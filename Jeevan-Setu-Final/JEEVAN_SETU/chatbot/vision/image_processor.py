"""
chatbot/vision/image_processor.py

Multimodal Image Processing, Knowledge-Asset Ingestion, and Isolated Patient
Medical Image Workflow for Jeevan Setu.

Responsibilities:
1. Knowledge-Base Image Processing (`process_knowledge_image_asset`,
   `ingest_knowledge_document_images`):
   - Processes embedded images extracted from approved PDF and DOCX documents by
     `chatbot/rag/document_loader.py`.
   - Preserves `document_id`, `image_id`, `source_document`, and PDF `page_number`
     (while keeping `page_number=None` for DOCX images without inventing page numbers).
   - Computes SHA-256 `content_hash` and skips duplicate processing when an
     identical image hash has already been processed.
   - Runs local OCR (`extract_text_from_image`) and optional Vision description
     (`analyze_image_with_vision`).
   - Persists metadata in MySQL `rag_document_images` (`RAGDocumentImage.upsert`)
     when available.
   - Converts OCR text and AI-generated visual descriptions into searchable text
     records, chunks them via `document_processor.process_document`, and indexes
     the text chunks into the shared `jeevan_setu_knowledge` ChromaDB collection
     (NEVER storing raw image bytes or base64 strings in ChromaDB).

2. Isolated Patient-Specific Clinical Image Workflow
   (`upload_and_process_patient_image`, `get_authorized_patient_images`,
   `get_authorized_patient_image_file`):
   - Strictly isolated from the shared knowledge base and NEVER indexed into
     `jeevan_setu_knowledge`.
   - Enforces authentication, RBAC role checks, and server-side patient access
     verification (`verify_patient_authorization`).
   - Strictly blocked in General Chat (`chat_mode="general"`).
   - Stores original validated files in an isolated patient directory with safe
     generated filenames and records metadata in `patient_medical_images`
     (`PatientMedicalImage`).
   - Enforces external privacy guardrails: patient images are NOT sent to
     external OpenRouter vision endpoints unless explicitly authorized.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from chatbot.rag.context_builder import (
    sanitize_untrusted_text,
    verify_patient_authorization,
)
from chatbot.rag.document_loader import (
    BACKEND_ROOT,
    KNOWLEDGE_BASE_DIR,
    UHID_PATTERN,
)
from chatbot.rag.document_processor import process_document
from chatbot.rag.vector_store import VectorStore
from chatbot.vision.image_loader import (
    DEFAULT_MAX_FILE_SIZE_BYTES,
    load_image,
    validate_safe_image_path,
)
from chatbot.vision.ocr_service import extract_text_from_image
from chatbot.vision.vision_service import analyze_image_with_vision

logger = logging.getLogger("jeevan_setu.vision.image_processor")

try:
    from models.chatbot_model import PatientMedicalImage, RAGDocumentImage
except (ImportError, ModuleNotFoundError):
    PatientMedicalImage = None
    RAGDocumentImage = None

try:
    from models.audit_log_model import AuditLog
except (ImportError, ModuleNotFoundError):
    AuditLog = None

DEFAULT_PATIENT_IMAGE_STORAGE_DIR = BACKEND_ROOT / "secure_storage" / "patient_images"
DEFAULT_GENERAL_IMAGE_STORAGE_DIR = BACKEND_ROOT / "secure_storage" / "general_images"

class ImageValidationError(ValueError):
    """Raised when an uploaded image fails validation (magic bytes, format, size, dimensions)."""
    pass


class ImageAuthorizationError(PermissionError):
    """Raised when an image upload or access fails RBAC or patient authorization."""
    pass


VALID_PATIENT_IMAGE_TYPES = (
    "ecg",
    "xray",
    "ct_scan",
    "lab_report",
    "monitor_snapshot",
    "clinical_chart",
    "other",
)
VALID_PATIENT_ACCESS_LEVELS = ("clinical_staff", "doctor_only", "admin_only")
UPLOAD_ALLOWED_ROLES = ("admin", "superadmin", "doctor", "nurse", "command_center")


# =============================================================================
# 1. KNOWLEDGE-BASE IMAGE PROCESSING & CHROMADB TEXT INDEXING
# =============================================================================

def build_multimodal_searchable_text(
    *,
    document_id: str,
    image_id: str,
    source_document: str,
    page_number: Optional[int],
    ocr_result: Dict[str, Any],
    vision_result: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Combine OCR text and AI-generated visual descriptions into a structured,
    explicitly labeled searchable text block suitable for `document_processor`
    and ChromaDB text indexing. Never includes raw image bytes or base64 strings.
    """
    sections: List[str] = []
    page_label = f", Page {page_number}" if page_number is not None else ""
    header = f"[Multimodal Document Asset: {image_id} | Source: {source_document}{page_label} | Doc ID: {document_id}]"
    sections.append(header)

    ocr_text = (ocr_result or {}).get("ocr_text", "").strip()
    if ocr_text:
        sections.append(f"[OCR Extracted Text]:\n{ocr_text}")

    if vision_result and vision_result.get("vision_status") == "completed":
        vis_desc = (vision_result.get("vision_description") or "").strip()
        if vis_desc:
            sections.append(vis_desc)

    if len(sections) <= 1:
        return ""
    return "\n\n".join(sections)


def process_knowledge_image_asset(
    asset_meta: Dict[str, Any],
    *,
    base_dir: Optional[Union[str, Path]] = None,
    enable_ocr: bool = True,
    enable_vision: bool = True,
    ocr_backend: Optional[Callable[..., Any]] = None,
    vision_caller: Optional[Callable[..., Dict[str, Any]]] = None,
    seen_hashes: Optional[ Dict[str, Dict[str, Any]] ] = None,
    sync_mysql: bool = True,
) -> Dict[str, Any]:
    """
    Process a single extracted PDF or DOCX image asset from `document_loader.py`.

    Preserves:
    - `document_id`
    - `image_id`
    - `source_document`
    - `page_number` (preserved for PDF; kept `None` for DOCX without inventing page numbers)
    - `content_hash` (SHA-256)
    - `ocr_status` & `ocr_text`
    - `vision_status` & `vision_description`
    - `ai_generated_description` indicator
    """
    if not isinstance(asset_meta, dict):
        raise ValueError("asset_meta must be a dictionary.")

    kb_root = Path(base_dir).resolve() if base_dir else KNOWLEDGE_BASE_DIR.resolve()
    rel_asset_path = str(asset_meta.get("asset_path") or "").strip()
    if not rel_asset_path:
        raise ValueError("asset_meta is missing 'asset_path'.")

    source_document = str(asset_meta.get("source_document") or asset_meta.get("source") or "unknown").replace("\\", "/")
    document_id = str(asset_meta.get("document_id") or "UNKNOWN_DOC").strip()
    page_number = asset_meta.get("page_number")
    if page_number is not None:
        try:
            page_number = max(1, int(page_number))
        except (ValueError, TypeError):
            page_number = None

    image_index = int(asset_meta.get("image_index") or 1)
    full_path = kb_root / rel_asset_path

    # 1. Validate & load image safely within kb_root
    try:
        img_info = load_image(full_path, base_dir=kb_root)
    except Exception as exc:
        logger.warning("Failed to load knowledge image asset '%s': %s", rel_asset_path, exc)
        return {
            "image_id": asset_meta.get("image_id") or f"img_invalid_{image_index}",
            "document_id": document_id,
            "source_document": source_document,
            "page_number": page_number,
            "asset_path": rel_asset_path,
            "processing_status": "failed",
            "ocr_status": "failed",
            "ocr_text": "",
            "vision_status": "skipped",
            "vision_description": "",
            "ai_generated_description": False,
            "searchable_text": "",
            "duplicate_skipped": False,
            "error": str(exc),
        }

    content_hash = img_info["content_hash"]
    image_id = str(
        asset_meta.get("image_id")
        or f"img_{document_id}_{f'p{page_number}_' if page_number is not None else ''}{image_index}_{content_hash[:10]}"
    )

    # 2. Deduplication check by SHA-256 content_hash
    if seen_hashes is not None and content_hash in seen_hashes:
        cached = seen_hashes[content_hash]
        dup_result = {
            **cached,
            "image_id": image_id,
            "document_id": document_id,
            "source_document": source_document,
            "page_number": page_number,
            "asset_path": rel_asset_path,
            "duplicate_skipped": True,
        }
        return dup_result

    # 3. Run local OCR
    if enable_ocr:
        ocr_res = extract_text_from_image(
            img_info,
            image_id=image_id,
            document_id=document_id,
            source_path=source_document,
            page_number=page_number,
            ocr_backend=ocr_backend,
        )
    else:
        ocr_res = {
            "ocr_status": "skipped",
            "ocr_text": "",
            "mean_confidence": None,
            "has_sufficient_text": False,
        }

    # Reject if OCR text contains identifiable patient UHID in shared knowledge base
    if UHID_PATTERN.search(ocr_res.get("ocr_text") or ""):
        return {
            "image_id": image_id,
            "document_id": document_id,
            "source_document": source_document,
            "page_number": page_number,
            "asset_path": rel_asset_path,
            "processing_status": "rejected_patient_uhid",
            "ocr_status": "failed",
            "ocr_text": "",
            "vision_status": "skipped",
            "vision_description": "",
            "ai_generated_description": False,
            "searchable_text": "",
            "duplicate_skipped": False,
            "error": "Rejected knowledge-base image containing identifiable patient UHID.",
        }

    # 4. Run Vision description where enabled and supported
    if enable_vision:
        vision_res = analyze_image_with_vision(
            img_info,
            image_scope="knowledge_base",
            prompt_context=f"Document: {source_document}",
            image_id=image_id,
            document_id=document_id,
            source_path=source_document,
            page_number=page_number,
            vision_caller=vision_caller,
        )
    else:
        vision_res = {
            "vision_status": "skipped",
            "vision_description": "",
            "content_type": "other",
            "ai_generated": False,
            "vision_model": None,
        }

    searchable_text = build_multimodal_searchable_text(
        document_id=document_id,
        image_id=image_id,
        source_document=source_document,
        page_number=page_number,
        ocr_result=ocr_res,
        vision_result=vision_res,
    )

    overall_status = (
        "completed"
        if (ocr_res.get("ocr_status") == "completed" or vision_res.get("vision_status") == "completed")
        else ("failed" if ocr_res.get("ocr_status") == "failed" and vision_res.get("vision_status") == "failed" else "partial")
    )

    result_record: Dict[str, Any] = {
        "image_id": image_id,
        "document_id": document_id,
        "source_document": source_document,
        "page_number": page_number,
        "image_index": image_index,
        "asset_path": rel_asset_path,
        "mime_type": img_info["mime_type"],
        "image_format": img_info["image_format"],
        "width": img_info["width"],
        "height": img_info["height"],
        "file_size_bytes": img_info["file_size_bytes"],
        "content_hash": content_hash,
        "ocr_status": ocr_res.get("ocr_status", "skipped"),
        "ocr_text": ocr_res.get("ocr_text", ""),
        "ocr_confidence": ocr_res.get("mean_confidence"),
        "vision_status": vision_res.get("vision_status", "skipped"),
        "vision_description": vision_res.get("vision_description", ""),
        "vision_model": vision_res.get("vision_model"),
        "content_type": vision_res.get("content_type", "document_image"),
        "ai_generated_description": bool(vision_res.get("ai_generated", False)),
        "clinician_verification_required": True,
        "searchable_text": searchable_text,
        "processing_status": overall_status,
        "duplicate_skipped": False,
        "error": ocr_res.get("error") or vision_res.get("error"),
    }

    if seen_hashes is not None:
        seen_hashes[content_hash] = dict(result_record)

    # 5. Synchronize with MySQL `rag_document_images` when available
    if sync_mysql and RAGDocumentImage is not None:
        try:
            db_ocr_status = (
                "completed"
                if result_record["ocr_status"] == "completed"
                else ("failed" if result_record["ocr_status"] == "failed" else "skipped")
            )
            db_vis_status = (
                "completed"
                if result_record["vision_status"] == "completed"
                else ("failed" if result_record["vision_status"] == "failed" else "skipped")
            )
            db_proc_status = "indexed" if searchable_text else ("failed" if overall_status == "failed" else "pending")
            RAGDocumentImage.upsert(
                image_id=image_id,
                document_id=document_id,
                source_document=source_document,
                asset_path=rel_asset_path,
                page_number=page_number,
                image_index=image_index,
                mime_type=img_info["mime_type"],
                image_format=img_info["image_format"],
                width=img_info["width"],
                height=img_info["height"],
                file_size_bytes=img_info["file_size_bytes"],
                content_hash=content_hash,
                ocr_status=db_ocr_status,
                ocr_text=result_record["ocr_text"] or None,
                vision_status=db_vis_status,
                vision_description=result_record["vision_description"] or None,
                vision_model=result_record["vision_model"],
                processing_status=db_proc_status,
                error_message=result_record["error"],
            )
        except Exception as exc:
            logger.debug("MySQL rag_document_images upsert skipped: %s", exc)

    return result_record


def ingest_knowledge_document_images(
    document_records: List[Dict[str, Any]],
    *,
    base_dir: Optional[Union[str, Path]] = None,
    vector_store: Optional[VectorStore] = None,
    enable_ocr: bool = True,
    enable_vision: bool = True,
    ocr_backend: Optional[Callable[..., Any]] = None,
    vision_caller: Optional[Callable[..., Dict[str, Any]]] = None,
    sync_mysql: bool = True,
) -> Dict[str, Any]:
    """
    End-to-end Phase 5 Multimodal Ingestion Pipeline for approved PDF and DOCX
    knowledge documents loaded by `document_loader.load_documents()`:

    1. Extracts `image_assets` from each approved document record.
    2. Validates, deduplicates, and runs OCR + Vision on each image.
    3. Converts useful OCR and visual descriptions into searchable text records
       preserving `document_id`, `image_id`, `source`, `page_number` (for PDF;
       `None` for DOCX), `ocr_status`, `vision_status`, `content_type`, and
       `ai_generated_description`.
    4. Chunks searchable text via `document_processor.process_document` and
       indexes the chunks into the approved ChromaDB knowledge collection via
       `VectorStore.add_chunks()` (never storing raw image bytes or base64 in ChromaDB).
    """
    kb_root = Path(base_dir).resolve() if base_dir else KNOWLEDGE_BASE_DIR.resolve()
    seen_hashes: Dict[str, Dict[str, Any]] = {}
    processed_images: List[Dict[str, Any]] = []
    multimodal_chunks: List[Dict[str, Any]] = []

    for doc in document_records or []:
        if not isinstance(doc, dict):
            continue

        # Only process approved document records that belong to the knowledge base
        source_rel = str(doc.get("source") or doc.get("metadata", {}).get("source") or "").strip()
        if not source_rel or ".." in Path(source_rel).parts:
            continue
        if UHID_PATTERN.search(str(doc.get("content") or "")):
            continue

        doc_id = str(doc.get("document_id") or doc.get("metadata", {}).get("document_id") or "UNKNOWN_DOC")
        category = str(doc.get("category") or doc.get("metadata", {}).get("category") or "general")
        file_type = str(doc.get("file_type") or doc.get("metadata", {}).get("file_type") or "pdf")
        doc_version = str(doc.get("document_version") or doc.get("metadata", {}).get("document_version") or "1.0")

        # Preserve PDF page number; do NOT invent page numbers for DOCX
        doc_page = doc.get("page_number")
        if file_type.lower() == "docx":
            doc_page = None

        raw_assets = (
            doc.get("image_assets")
            or doc.get("metadata", {}).get("image_assets")
            or []
        )
        if not isinstance(raw_assets, list) or not raw_assets:
            continue

        for idx, asset in enumerate(raw_assets, start=1):
            if not isinstance(asset, dict):
                continue
            enriched_asset = {
                **asset,
                "document_id": asset.get("document_id") or doc_id,
                "source_document": asset.get("source_document") or source_rel,
                "page_number": None if file_type.lower() == "docx" else (asset.get("page_number") or doc_page),
                "image_index": asset.get("image_index") or idx,
            }

            img_res = process_knowledge_image_asset(
                enriched_asset,
                base_dir=kb_root,
                enable_ocr=enable_ocr,
                enable_vision=enable_vision,
                ocr_backend=ocr_backend,
                vision_caller=vision_caller,
                seen_hashes=seen_hashes,
                sync_mysql=sync_mysql,
            )
            processed_images.append(img_res)

            searchable_text = img_res.get("searchable_text", "").strip()
            if not searchable_text or img_res.get("duplicate_skipped"):
                continue

            # Create a synthetic document record for `process_document()` to chunk
            asset_doc_record = {
                "document_id": doc_id,
                "document_version": doc_version,
                "source": source_rel,
                "category": category,
                "file_type": file_type,
                "page_number": img_res["page_number"],
                "content": searchable_text,
                "image_assets": [
                    {
                        "image_id": img_res["image_id"],
                        "document_id": doc_id,
                        "source_document": source_rel,
                        "page_number": img_res["page_number"],
                        "asset_path": img_res["asset_path"],
                        "image_format": img_res["image_format"],
                        "ocr_status": img_res["ocr_status"],
                        "vision_status": img_res["vision_status"],
                        "content_type": img_res["content_type"],
                        "ai_generated_description": img_res["ai_generated_description"],
                    }
                ],
                "metadata": {
                    "document_id": doc_id,
                    "document_version": doc_version,
                    "source": source_rel,
                    "category": category,
                    "file_type": file_type,
                    "page_number": img_res["page_number"],
                    "image_id": img_res["image_id"],
                    "ocr_status": img_res["ocr_status"],
                    "vision_status": img_res["vision_status"],
                    "content_type": img_res["content_type"],
                    "ai_generated_description": img_res["ai_generated_description"],
                },
            }

            chunks = process_document(asset_doc_record)
            for c_idx, ch in enumerate(chunks):
                # Make chunk_id unique per image asset so it doesn't collide with text-only chunks
                ch["chunk_id"] = f"{ch['chunk_id']}_{img_res['image_id']}_m{c_idx}"
                ch["metadata"]["chunk_id"] = ch["chunk_id"]
                ch["metadata"]["image_id"] = img_res["image_id"]
                ch["metadata"]["ocr_status"] = img_res["ocr_status"]
                ch["metadata"]["vision_status"] = img_res["vision_status"]
                ch["metadata"]["content_type"] = img_res["content_type"]
                ch["metadata"]["ai_generated_description"] = img_res["ai_generated_description"]
                multimodal_chunks.append(ch)

    indexed_Result: Dict[str, Any] = {"added": 0, "chunk_ids": []}
    if multimodal_chunks and vector_store is not None:
        raw_vs_res = vector_store.add_chunks(multimodal_chunks, sync_mysql=sync_mysql)
        if isinstance(raw_vs_res, list):
            indexed_Result = {"added": len(raw_vs_res), "chunk_ids": raw_vs_res}
        elif isinstance(raw_vs_res, dict):
            indexed_Result = raw_vs_res

    return {
        "images_processed": len(processed_images),
        "images": processed_images,
        "chunks_created": len(multimodal_chunks),
        "chunks": multimodal_chunks,
        "vector_store_summary": indexed_Result,
    }


# =============================================================================
# 2. ISOLATED PATIENT-SPECIFIC CLINICAL IMAGE WORKFLOW (PHASE 6 & 9)
# =============================================================================

# In-memory fallback store used only when MySQL `db` is offline/mocked in unit tests
_FALLBACK_PATIENT_IMAGE_STORE: Dict[int, Dict[str, Any]] = {}
_FALLBACK_IMAGE_COUNTER: int = 1000
_FALLBACK_GENERAL_IMAGE_STORE: Dict[str, Dict[str, Any]] = {}


def reset_fallback_patient_image_store() -> None:
    """Clear the in-memory test fallback store."""
    global _FALLBACK_IMAGE_COUNTER
    _FALLBACK_PATIENT_IMAGE_STORE.clear()
    _FALLBACK_GENERAL_IMAGE_STORE.clear()
    _FALLBACK_IMAGE_COUNTER = 1000


def upload_and_process_patient_image(
    *,
    patient_id: int,
    user_id: Union[int, str],
    user_role: str,
    image_source: Optional[Union[str, Path, bytes, io.BytesIO]] = None,
    file_bytes: Optional[bytes] = None,
    title: Optional[str] = None,
    image_type: str = "other",
    clinical_context: Optional[str] = None,
    access_level: str = "clinical_staff",
    chat_mode: str = "patient",
    filename_hint: Optional[str] = None,
    filename: Optional[str] = None,
    assigned_patient_id: Optional[Union[int, str]] = None,
    storage_dir: Optional[Union[str, Path]] = None,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    enable_ocr: bool = True,
    allow_external_patient_vision: Optional[bool] = None,
    enable_vision_llm: Optional[bool] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    ocr_backend: Optional[Callable[..., Any]] = None,
    vision_caller: Optional[Callable[..., Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Securely validate, store, and process an authorized patient-specific clinical
    image (ECG, X-ray, CT scan, lab report, monitor snapshot, clinical chart).

    Security & Isolation Guarantees:
    1. Strictly blocked in General Chat (`chat_mode="general"`).
    2. Only clinical staff (`admin`, `doctor`, `nurse`, `command_center`) can upload.
    3. Server-side RBAC patient authorization (`verify_patient_authorization`) is
       verified BEFORE reading or saving the image.
    4. Stored in an isolated directory (`secure_storage/patient_images/patient_<id>/`)
       outside `knowledge_base/` and NEVER indexed into the shared ChromaDB collection.
    5. External OpenRouter vision calls are disabled by default for patient images
       unless `allow_external_patient_vision=True`.
    """
    global _FALLBACK_IMAGE_COUNTER

    # Resolve parameter aliases
    if image_source is None and file_bytes is not None:
        image_source = file_bytes
    if filename_hint is None and filename is not None:
        filename_hint = filename
    if allow_external_patient_vision is None and enable_vision_llm is not None:
        allow_external_patient_vision = enable_vision_llm

    if image_source is None:
        raise ImageValidationError("No image data provided for patient upload.")

    # 1. Block General Chat
    mode_norm = str(chat_mode or "").strip().lower()
    if mode_norm != "patient":
        raise ImageAuthorizationError(
            "Patient-specific medical images cannot be uploaded or processed in General Chat mode."
        )

    # 2. Validate uploader role
    role_norm = str(user_role or "").strip().lower()
    if role_norm not in UPLOAD_ALLOWED_ROLES:
        raise ImageAuthorizationError(
            f"Role '{user_role}' is not authorized to upload patient medical images."
        )

    # 3. Validate patient_id and server-side RBAC patient access
    is_auth, auth_err = verify_patient_authorization(
        user_id=user_id,
        user_role=role_norm,
        patient_id=patient_id,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )
    if not is_auth:
        raise ImageAuthorizationError(auth_err or f"Unauthorized access to patient #{patient_id}.")

    pid_int = int(patient_id)
    uid_int = int(user_id)

    if not title:
        title = Path(filename_hint or "Clinical Image").stem or "Clinical Image"
    if not isinstance(title, str) or not title.strip():
        raise ImageValidationError("Image title must be a non-empty string.")
    clean_title, _ = sanitize_untrusted_text(title.strip())
    clean_ctx, _ = sanitize_untrusted_text(clinical_context or "") if clinical_context else ("", [])

    img_type_norm = str(image_type or "other").strip().lower()
    if img_type_norm not in VALID_PATIENT_IMAGE_TYPES:
        img_type_norm = "other"

    acc_level_norm = str(access_level or "clinical_staff").strip().lower()
    if acc_level_norm not in VALID_PATIENT_ACCESS_LEVELS:
        acc_level_norm = "clinical_staff"

    # 4. Validate image content, magic bytes, size, and dimensions
    try:
        img_info = load_image(
            image_source,
            filename_hint=filename_hint,
            max_file_size_bytes=max_file_size_bytes,
        )
    except ValueError as val_err:
        raise ImageValidationError(str(val_err)) from val_err
    except PermissionError as perm_err:
        raise ImageAuthorizationError(str(perm_err)) from perm_err

    content_hash = img_info["content_hash"]
    ext = img_info["image_format"]

    # 5. Store in isolated patient directory (never inside knowledge_base)
    root_storage = Path(storage_dir).resolve() if storage_dir else DEFAULT_PATIENT_IMAGE_STORAGE_DIR.resolve()
    kb_resolved = KNOWLEDGE_BASE_DIR.resolve()
    if root_storage.is_relative_to(kb_resolved):
        raise ImageAuthorizationError(
            "Security violation: patient images must never be stored inside the shared knowledge_base directory."
        )

    patient_dir = (root_storage / f"patient_{pid_int}").resolve()
    if not patient_dir.is_relative_to(root_storage):
        raise ImageAuthorizationError("Invalid patient storage directory resolution.")
    patient_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"patient_{pid_int}_{img_type_norm}_{content_hash[:12]}.{ext}"
    target_file_path = (patient_dir / safe_filename).resolve()
    if not target_file_path.is_relative_to(patient_dir):
        raise ImageAuthorizationError("Unsafe target filename blocked.")

    if not target_file_path.exists():
        target_file_path.write_bytes(img_info["image_bytes"])

    rel_secure_path = f"patient_{pid_int}/{safe_filename}"

    # 6. Run local OCR
    if enable_ocr:
        ocr_res = extract_text_from_image(
            img_info,
            image_id=safe_filename,
            document_id=None,
            source_path=rel_secure_path,
            ocr_backend=ocr_backend,
        )
    else:
        ocr_res = {"ocr_status": "skipped", "ocr_text": "", "mean_confidence": None}

    # 7. Vision processing (respects privacy guardrail: skipped by default for patient images)
    vision_res = analyze_image_with_vision(
        img_info,
        image_scope="patient",
        prompt_context=f"Patient Clinical Image ({img_type_norm}): {clean_title}",
        image_id=safe_filename,
        source_path=rel_secure_path,
        allow_external_patient_vision=allow_external_patient_vision,
        vision_caller=vision_caller,
    )

    if vision_res.get("vision_status") != "completed":
        logger.info(
            "Patient #%d image '%s' vision status: %s (reason: %s)",
            pid_int,
            safe_filename,
            vision_res.get("vision_status"),
            vision_res.get("failure_reason") or "unavailable",
        )
    else:
        logger.info(
            "Patient #%d image '%s' vision analysis completed successfully with model '%s'.",
            pid_int,
            safe_filename,
            vision_res.get("vision_model"),
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    db_ocr_status = "completed" if ocr_res.get("ocr_status") == "completed" else (
        "failed" if ocr_res.get("ocr_status") == "failed" else "not_required"
    )
    db_vis_status = "completed" if vision_res.get("vision_status") == "completed" else (
        "failed" if vision_res.get("vision_status") == "failed" else "not_required"
    )

    patient_image_id: Optional[int] = None
    if PatientMedicalImage is not None:
        try:
            inserted_id = PatientMedicalImage.create(
                patient_id=pid_int,
                uploaded_by=uid_int,
                image_type=img_type_norm,
                title=clean_title,
                clinical_context=clean_ctx or None,
                secure_file_path=rel_secure_path,
                mime_type=img_info["mime_type"],
                image_format=ext,
                file_size_bytes=img_info["file_size_bytes"],
                content_hash=content_hash,
                ocr_status=db_ocr_status,
                ocr_text=ocr_res.get("ocr_text") or None,
                vision_status=db_vis_status,
                vision_description=vision_res.get("vision_description") or None,
                vision_model=vision_res.get("vision_model"),
                access_level=acc_level_norm,
                is_active=True,
            )
            if isinstance(inserted_id, int) and inserted_id > 0:
                patient_image_id = inserted_id
        except Exception as exc:
            logger.debug("MySQL PatientMedicalImage.create fallback used: %s", exc)

    if patient_image_id is None:
        _FALLBACK_IMAGE_COUNTER += 1
        patient_image_id = _FALLBACK_IMAGE_COUNTER

    record = {
        "patient_image_id": patient_image_id,
        "image_id": str(patient_image_id),
        "patient_id": pid_int,
        "uploaded_by": uid_int,
        "image_type": img_type_norm,
        "title": clean_title,
        "clinical_context": clean_ctx or None,
        "secure_file_path": rel_secure_path,
        "absolute_file_path": str(target_file_path),
        "image_url": f"/chatbot/image/{patient_image_id}/view",
        "mime_type": img_info["mime_type"],
        "image_format": ext,
        "width": img_info["width"],
        "height": img_info["height"],
        "file_size_bytes": img_info["file_size_bytes"],
        "content_hash": content_hash,
        "ocr_status": ocr_res.get("ocr_status"),
        "ocr_text": ocr_res.get("ocr_text") or "",
        "ocr_confidence": ocr_res.get("mean_confidence"),
        "vision_status": vision_res.get("vision_status"),
        "vision_description": vision_res.get("vision_description") or "",
        "vision_error": vision_res.get("error") or "",
        "vision_model": vision_res.get("vision_model"),
        "ai_generated_description": bool(vision_res.get("ai_generated", False)),
        "clinician_verification_required": True,
        "access_level": acc_level_norm,
        "is_active": True,
        "shared_chromadb_indexed": False,  # Strictly NEVER indexed into shared ChromaDB
        "created_at": now_iso,
    }
    _FALLBACK_PATIENT_IMAGE_STORE[patient_image_id] = record

    if AuditLog is not None:
        try:
            AuditLog.log(
                user_id=uid_int,
                action="PATIENT_IMAGE_UPLOAD",
                entity_type="patient_medical_image",
                entity_id=patient_image_id,
                description=f"Uploaded {img_type_norm} image for patient #{pid_int}",
            )
        except Exception:
            pass

    try:
        set_active_image_context(user_id=user_id, patient_id=pid_int, mode="patient", image_info=record)
    except Exception:
        pass

    return record


def get_authorized_patient_images(
    *,
    patient_id: int,
    user_id: Union[int, str],
    user_role: str,
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Retrieve metadata, OCR text, and vision descriptions for a patient's medical
    images after enforcing:
    1. `chat_mode == "patient"` (General Chat is strictly blocked).
    2. Server-side RBAC patient authorization (`verify_patient_authorization`).
    3. Role-based `access_level` filtering (`clinical_staff`, `doctor_only`, `admin_only`).
    """
    mode_norm = str(chat_mode or "").strip().lower()
    if mode_norm != "patient":
        raise PermissionError(
            "Patient-specific medical images cannot be accessed in General Chat mode."
        )

    role_norm = str(user_role or "").strip().lower()
    is_auth, auth_err = verify_patient_authorization(
        user_id=user_id,
        user_role=role_norm,
        patient_id=patient_id,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
    )
    if not is_auth:
        raise PermissionError(auth_err or f"Unauthorized access to patient #{patient_id} images.")

    if role_norm == "attendant":
        return []

    pid_int = int(patient_id)
    results: List[Dict[str, Any]] = []

    if PatientMedicalImage is not None:
        try:
            db_rows = PatientMedicalImage.get_by_patient(
                patient_id=pid_int,
                active_only=True,
                chat_mode="patient",
                user_role=role_norm,
                limit=limit,
            )
            if db_rows:
                results.extend(db_rows)
        except Exception as exc:
            logger.debug("MySQL PatientMedicalImage query fallback used: %s", exc)

    if not results:
        for rec in _FALLBACK_PATIENT_IMAGE_STORE.values():
            if rec.get("patient_id") != pid_int or not rec.get("is_active", True):
                continue
            acc = rec.get("access_level", "clinical_staff")
            if role_norm in ("admin", "superadmin"):
                results.append(dict(rec))
            elif role_norm == "doctor" and acc in ("clinical_staff", "doctor_only"):
                results.append(dict(rec))
            elif role_norm in ("nurse", "command_center") and acc == "clinical_staff":
                results.append(dict(rec))

    return results[: max(1, int(limit))]


def get_authorized_patient_image_file(
    *,
    patient_image_id: Optional[Union[int, str]] = None,
    image_id: Optional[Union[int, str]] = None,
    patient_id: int,
    user_id: Union[int, str],
    user_role: str,
    chat_mode: str = "patient",
    assigned_patient_id: Optional[Union[int, str]] = None,
    storage_dir: Optional[Union[str, Path]] = None,
    authorization_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
) -> Path:
    """
    Return the validated on-disk `Path` for an authorized patient medical image,
    verifying chat mode, patient RBAC, role access level, and storage directory
    containment.
    """
    raw_img_id = patient_image_id if patient_image_id is not None else image_id
    if raw_img_id is None:
        raise ValueError("patient_image_id or image_id is required.")
    
    digits = re.sub(r"[^\d]", "", str(raw_img_id))
    target_id_int = int(digits) if digits else -1

    authorized_list = get_authorized_patient_images(
        patient_id=patient_id,
        user_id=user_id,
        user_role=user_role,
        chat_mode=chat_mode,
        assigned_patient_id=assigned_patient_id,
        authorization_fn=authorization_fn,
        limit=100,
    )
    matched = next(
        (img for img in authorized_list if int(img.get("patient_image_id", -1)) == target_id_int or str(img.get("image_id", "")) == str(raw_img_id)),
        None,
    )
    if matched is None:
        raise PermissionError(
            f"Access denied or image #{raw_img_id} not found for patient #{patient_id}."
        )

    root_storage = Path(storage_dir).resolve() if storage_dir else DEFAULT_PATIENT_IMAGE_STORAGE_DIR.resolve()
    rel_path = matched.get("secure_file_path")
    if not rel_path:
        raise FileNotFoundError("Image secure_file_path is missing.")

    return validate_safe_image_path(root_storage / rel_path, base_dir=root_storage)


# =============================================================================
# 3. GENERAL CHAT CLINICAL & REFERENCE IMAGE WORKFLOW
# =============================================================================

def process_general_chat_image(
    *,
    image_source: Optional[Union[str, Path, bytes, io.BytesIO]] = None,
    file_bytes: Optional[bytes] = None,
    user_id: Optional[Union[int, str]] = None,
    user_role: Optional[str] = None,
    title: Optional[str] = None,
    filename_hint: Optional[str] = None,
    filename: Optional[str] = None,
    chat_mode: str = "general",
    storage_dir: Optional[Union[str, Path]] = None,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    enable_ocr: bool = True,
    enable_vision: bool = True,
    enable_vision_llm: Optional[bool] = None,
    ocr_backend: Optional[Callable[..., Any]] = None,
    vision_caller: Optional[Callable[..., Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Process an image uploaded in General Chat mode.

    Privacy & Security Guarantees:
    1. Strictly isolated: NEVER accesses or writes to patient tables or patient directories.
    2. Runs local OCR and vision description on medical reference images / charts.
    3. Saves into isolated 'secure_storage/general_images/' directory.
    4. Generates a safe general image ID and returns non-patient metadata.
    """
    if image_source is None and file_bytes is not None:
        image_source = file_bytes
    if filename_hint is None and filename is not None:
        filename_hint = filename
    if enable_vision_llm is not None:
        enable_vision = bool(enable_vision_llm)

    if image_source is None:
        raise ImageValidationError("No image data provided for General Chat upload.")

    if not title:
        title = Path(filename_hint or "Reference Image").stem or "Reference Image"
    clean_title, _ = sanitize_untrusted_text(str(title).strip())

    try:
        img_info = load_image(
            image_source,
            filename_hint=filename_hint,
            max_file_size_bytes=max_file_size_bytes,
        )
    except ValueError as val_err:
        raise ImageValidationError(str(val_err)) from val_err
    except PermissionError as perm_err:
        raise ImageAuthorizationError(str(perm_err)) from perm_err

    content_hash = img_info["content_hash"]
    ext = img_info["image_format"]
    gen_id = f"gen_{content_hash[:12]}"

    root_storage = Path(storage_dir).resolve() if storage_dir else DEFAULT_GENERAL_IMAGE_STORAGE_DIR.resolve()
    kb_resolved = KNOWLEDGE_BASE_DIR.resolve()
    if root_storage.is_relative_to(kb_resolved):
        raise ImageAuthorizationError(
            "Security violation: general images must never be stored inside the knowledge_base directory."
        )
    root_storage.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{gen_id}.{ext}"
    target_file_path = (root_storage / safe_filename).resolve()
    if not target_file_path.is_relative_to(root_storage):
        raise ImageAuthorizationError("Unsafe target filename blocked.")

    if not target_file_path.exists():
        target_file_path.write_bytes(img_info["image_bytes"])

    # 1. OCR
    if enable_ocr:
        ocr_res = extract_text_from_image(
            img_info,
            image_id=safe_filename,
            document_id=None,
            source_path=safe_filename,
            ocr_backend=ocr_backend,
        )
    else:
        ocr_res = {"ocr_status": "skipped", "ocr_text": "", "mean_confidence": None}

    # 2. Vision analysis (allowed for general non-patient clinical reference images)
    if enable_vision:
        vision_res = analyze_image_with_vision(
            img_info,
            image_scope="general",
            prompt_context=f"General Clinical Reference Image: {clean_title}",
            image_id=safe_filename,
            source_path=safe_filename,
            allow_external_patient_vision=True,
            vision_caller=vision_caller,
        )
    else:
        vision_res = {"vision_status": "skipped", "vision_description": "", "vision_model": None}

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "image_id": gen_id,
        "patient_image_id": None,
        "patient_id": None,
        "is_patient_data": False,
        "title": clean_title,
        "secure_file_path": safe_filename,
        "absolute_file_path": str(target_file_path),
        "image_url": f"/chatbot/image/{gen_id}/view",
        "mime_type": img_info["mime_type"],
        "image_format": ext,
        "width": img_info["width"],
        "height": img_info["height"],
        "file_size_bytes": img_info["file_size_bytes"],
        "content_hash": content_hash,
        "ocr_status": ocr_res.get("ocr_status"),
        "ocr_text": ocr_res.get("ocr_text") or "",
        "ocr_confidence": ocr_res.get("mean_confidence"),
        "vision_status": vision_res.get("vision_status"),
        "vision_description": vision_res.get("vision_description") or "",
        "vision_error": vision_res.get("error") or "",
        "vision_model": vision_res.get("vision_model"),
        "ai_generated_description": bool(vision_res.get("ai_generated", False)),
        "clinician_verification_required": True,
        "chat_mode": "general",
        "shared_chromadb_indexed": False,
        "created_at": now_iso,
    }
    _FALLBACK_GENERAL_IMAGE_STORE[gen_id] = record
    try:
        set_active_image_context(user_id=user_id, patient_id=None, mode="general", image_info=record)
    except Exception:
        pass
    return record


def get_general_chat_image_file(
    image_id: str,
    storage_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """Return validated on-disk Path for a general chat image."""
    root_storage = Path(storage_dir).resolve() if storage_dir else DEFAULT_GENERAL_IMAGE_STORAGE_DIR.resolve()
    clean_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "", str(image_id))
    rec = _FALLBACK_GENERAL_IMAGE_STORE.get(clean_id)
    if rec and rec.get("absolute_file_path"):
        p = Path(rec["absolute_file_path"]).resolve()
        if p.exists() and p.is_relative_to(root_storage):
            return p
    candidates = list(root_storage.glob(f"{clean_id}.*"))
    if candidates:
        return validate_safe_image_path(candidates[0], base_dir=root_storage)
    raise FileNotFoundError(f"General chat image '{image_id}' not found.")


# =============================================================================
# 3. ACTIVE IMAGE CONTEXT MANAGER FOR SESSION & FOLLOW-UP IMAGE Q&A
# =============================================================================

class ActiveImageContextManager:
    """
    Thread-safe in-memory session manager for tracking active image contexts
    across conversation turns for follow-up question answering.
    Keyed by (user_id, patient_id_or_none, mode).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._contexts: Dict[Tuple[str, Optional[int], str], Dict[str, Any]] = {}

    def _make_key(self, user_id: Any, patient_id: Any, mode: str) -> Tuple[str, Optional[int], str]:
        u_str = str(user_id if user_id is not None else "anon").strip()
        p_int = int(patient_id) if patient_id not in (None, "", "null") else None
        m_str = str(mode or "patient").strip().lower()
        return (u_str, p_int, m_str)

    def set_active_image(
        self,
        user_id: Any,
        patient_id: Any,
        mode: str,
        image_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Set or replace the currently active image context for a session."""
        key = self._make_key(user_id, patient_id, mode)
        ctx = {
            "image_id": image_info.get("image_id"),
            "file_path": image_info.get("absolute_file_path") or image_info.get("file_path"),
            "filename": image_info.get("filename"),
            "title": image_info.get("title") or "Uploaded Image",
            "image_type": image_info.get("image_type") or "clinical_image",
            "mime_type": image_info.get("mime_type") or "image/jpeg",
            "width": image_info.get("width"),
            "height": image_info.get("height"),
            "image_url": image_info.get("image_url"),
            "ocr_text": image_info.get("ocr_text") or "",
            "vision_description": image_info.get("vision_description") or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "history": [],
        }
        with self._lock:
            self._contexts[key] = ctx
        return ctx

    def get_active_image(
        self,
        user_id: Any,
        patient_id: Any,
        mode: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve active image context if present."""
        key = self._make_key(user_id, patient_id, mode)
        with self._lock:
            ctx = self._contexts.get(key)
            return dict(ctx) if ctx else None

    def clear_active_image(
        self,
        user_id: Any,
        patient_id: Any,
        mode: str,
    ) -> bool:
        """Clear the active image context."""
        key = self._make_key(user_id, patient_id, mode)
        with self._lock:
            return bool(self._contexts.pop(key, None))

    def add_turn(
        self,
        user_id: Any,
        patient_id: Any,
        mode: str,
        question: str,
        answer: str,
    ) -> None:
        """Add a Q&A turn to active image context history (keeps last 5 turns)."""
        key = self._make_key(user_id, patient_id, mode)
        with self._lock:
            ctx = self._contexts.get(key)
            if ctx:
                ctx.setdefault("history", []).append({
                    "question": str(question or "").strip(),
                    "answer": str(answer or "").strip(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                if len(ctx["history"]) > 5:
                    ctx["history"] = ctx["history"][-5:]


_ACTIVE_IMAGE_CONTEXT_MANAGER = ActiveImageContextManager()


def set_active_image_context(
    user_id: Any,
    patient_id: Any,
    mode: str,
    image_info: Dict[str, Any],
) -> Dict[str, Any]:
    return _ACTIVE_IMAGE_CONTEXT_MANAGER.set_active_image(user_id, patient_id, mode, image_info)


def get_active_image_context(
    user_id: Any,
    patient_id: Any,
    mode: str,
) -> Optional[Dict[str, Any]]:
    return _ACTIVE_IMAGE_CONTEXT_MANAGER.get_active_image(user_id, patient_id, mode)


def clear_active_image_context(
    user_id: Any,
    patient_id: Any,
    mode: str,
) -> bool:
    return _ACTIVE_IMAGE_CONTEXT_MANAGER.clear_active_image(user_id, patient_id, mode)


def add_image_qa_turn(
    user_id: Any,
    patient_id: Any,
    mode: str,
    question: str,
    answer: str,
) -> None:
    _ACTIVE_IMAGE_CONTEXT_MANAGER.add_turn(user_id, patient_id, mode, question, answer)


__all__ = [
    "ActiveImageContextManager",
    "DEFAULT_GENERAL_IMAGE_STORAGE_DIR",
    "DEFAULT_PATIENT_IMAGE_STORAGE_DIR",
    "ImageAuthorizationError",
    "ImageValidationError",
    "UPLOAD_ALLOWED_ROLES",
    "VALID_PATIENT_ACCESS_LEVELS",
    "VALID_PATIENT_IMAGE_TYPES",
    "add_image_qa_turn",
    "build_multimodal_searchable_text",
    "clear_active_image_context",
    "get_active_image_context",
    "get_authorized_patient_image_file",
    "get_authorized_patient_images",
    "get_general_chat_image_file",
    "ingest_knowledge_document_images",
    "process_general_chat_image",
    "process_knowledge_image_asset",
    "reset_fallback_patient_image_store",
    "set_active_image_context",
    "upload_and_process_patient_image",
]

