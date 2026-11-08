"""
chatbot/rag/vector_store.py — Persistent ChromaDB Vector Store for Jeevan Setu RAG.

Manages persistent vector storage in `JEEVAN_SETU/vector_storage/` using ChromaDB's
`PersistentClient` and 384-dimensional embeddings from `chatbot/rag/embedding_service.py`
(`sentence-transformers/all-MiniLM-L6-v2`).

Key Capabilities:
- Persistent local ChromaDB storage (`JEEVAN_SETU/vector_storage/`, collection `jeevan_setu_knowledge`)
  with cosine similarity (`hnsw:space = "cosine"`).
- Single-chunk (`add_chunk`) and batch (`add_documents`, `add_chunks`) ingestion with automatic
  384-d finite vector validation and unchanged-chunk embedding reuse (idempotent ingestion).
- Source & version traceability on every stored and retrieved record (`chunk_id`, `document_id`,
  `document_version`, `source`, `category`, `file_type`, `page_number`, `chunk_index`,
  `content_hash`, and serialized `image_assets` references).
- Safe metadata serialization for complex list/dict fields (e.g., `image_assets`) while rejecting
  raw image bytes (`bytes`/`bytearray`), base64 image data URIs, and patient-identifiable data (`UHID` / `patient_id`).
- Non-destructive document version management (`delete_chunks_by_document`) that never deletes other
  documents or older versions automatically unless explicitly requested.
- Optional MySQL Migration 009 metadata synchronization (`sync_mysql=True`) using `RAGDocument`,
  `RAGDocumentImage`, and `RAGDocumentChunk` in `models/chatbot_model.py`, with graceful fallback
  when MySQL is not active or `sync_mysql=False`.
"""

import hashlib
import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from chatbot.rag.embedding_service import (
    EXPECTED_EMBEDDING_DIMENSION,
    MODEL_NAME,
    get_embedding,
    get_embeddings,
)

logger = logging.getLogger("jeevan_setu.rag.vector_store")

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
VECTOR_STORAGE_DIR = BACKEND_ROOT / "vector_storage"
DEFAULT_COLLECTION_NAME = "jeevan_setu_knowledge"
DEFAULT_DOCUMENT_VERSION = "1.0"
DEFAULT_SIMILARITY_SPACE = "cosine"

# Metadata scalar types allowed natively by ChromaDB
ALLOWED_METADATA_VALUE_TYPES = (str, int, float, bool)

# Complex metadata keys that may be safely serialized to deterministic JSON strings
# (provided they do not contain binary bytes, base64 image blobs, or patient identifiers)
SERIALIZABLE_METADATA_KEYS = frozenset({
    "image_assets",
    "image_ids",
    "tags",
    "sections",
})

# Prohibited metadata keys / patterns to prevent storing identifiable patient data
PROHIBITED_PATIENT_METADATA_KEYS = frozenset({
    "patient_id",
    "patient_image_id",
    "patient_name",
    "uhid",
    "ews_score",
    "heart_rate",
    "spo2",
    "systolic_bp",
    "diastolic_bp",
})
UHID_PATTERN = re.compile(r"\bUHID-\d{4}-\d{5}\b", re.IGNORECASE)
BASE64_IMAGE_URI_PATTERN = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+", re.IGNORECASE)


def get_vector_storage_dir(storage_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolve and ensure the persistent vector storage directory exists."""
    target = Path(storage_dir).resolve() if storage_dir else VECTOR_STORAGE_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _compute_text_hash(text: str) -> str:
    """Compute SHA-256 hex digest of a document chunk string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _infer_file_type_from_source(source: str, fallback: str = "txt") -> str:
    """Infer canonical file_type from source path extension."""
    ext = Path(str(source or "")).suffix.lower()
    ext_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".txt": "txt",
        ".md": "markdown",
        ".markdown": "markdown",
        ".json": "json",
    }
    return ext_map.get(ext, fallback)


def _derive_document_id_from_source(source: str, page_number: Optional[int] = None) -> str:
    """Derive a deterministic document_id when not explicitly provided in metadata."""
    norm_source = str(source or "unknown").replace("\\", "/").strip() or "unknown"
    key = f"{norm_source}#p{page_number}" if page_number is not None else norm_source
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(norm_source).stem).strip("_").lower() or "doc"
    if page_number is not None:
        return f"doc_{stem}_p{page_number}_{digest}"
    return f"doc_{stem}_{digest}"


def validate_embedding_vector(
    vector: Sequence[float],
    expected_dim: int = EXPECTED_EMBEDDING_DIMENSION,
) -> List[float]:
    """
    Validate that an embedding vector is a sequence of `expected_dim` (384) finite float values.

    Raises:
        ValueError: If vector is not a list/tuple, has wrong dimension, or contains non-finite values.
    """
    if not isinstance(vector, (list, tuple)):
        raise ValueError(f"Embedding vector must be a list or tuple, got {type(vector).__name__}.")
    if len(vector) != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {len(vector)}."
        )
    cleaned_vec: List[float] = []
    for idx, val in enumerate(vector):
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"Embedding value at index {idx} must be numeric, got {type(val).__name__}.")
        f_val = float(val)
        if not math.isfinite(f_val):
            raise ValueError(f"Embedding value at index {idx} is non-finite ({val}).")
        cleaned_vec.append(f_val)
    return cleaned_vec


def _sanitize_and_serialize_image_assets(raw_assets: Any) -> Tuple[str, str, int]:
    """
    Validate a list of image asset reference dicts (or comma-separated IDs) and return:
    `(serialized_json_str, comma_separated_ids, image_count)`.

    Rejects binary image bytes (`bytes`/`bytearray`), base64 image data URIs, and patient-specific fields.
    """
    if not raw_assets:
        return "[]", "", 0

    if isinstance(raw_assets, str):
        stripped = raw_assets.strip()
        if not stripped or stripped == "[]":
            return "[]", "", 0
        if BASE64_IMAGE_URI_PATTERN.search(stripped):
            raise ValueError("Base64 image data cannot be stored in ChromaDB metadata.")
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                raw_assets = parsed
            else:
                ids = [s.strip() for s in stripped.split(",") if s.strip()]
                return json.dumps([{"image_id": i} for i in ids]), ",".join(ids), len(ids)
        except Exception:
            ids = [s.strip() for s in stripped.split(",") if s.strip()]
            return json.dumps([{"image_id": i} for i in ids]), ",".join(ids), len(ids)

    if not isinstance(raw_assets, (list, tuple)):
        raise ValueError("image_assets must be a list of image reference dicts or strings.")

    clean_list: List[Dict[str, Any]] = []
    image_ids: List[str] = []
    for item in raw_assets:
        if isinstance(item, (bytes, bytearray)):
            raise ValueError("Raw binary image bytes cannot be stored in ChromaDB metadata.")
        if isinstance(item, str):
            if BASE64_IMAGE_URI_PATTERN.search(item):
                raise ValueError("Base64 image data cannot be stored in ChromaDB metadata.")
            if item.strip():
                clean_list.append({"image_id": item.strip()})
                image_ids.append(item.strip())
            continue
        if not isinstance(item, dict):
            raise ValueError(f"Invalid element in image_assets: {type(item).__name__}.")

        for k, v in item.items():
            if str(k).lower() in PROHIBITED_PATIENT_METADATA_KEYS:
                raise ValueError(f"Prohibited patient field '{k}' in image_assets.")
            if isinstance(v, (bytes, bytearray)):
                raise ValueError("Raw binary image bytes cannot be stored in image_assets.")
            if isinstance(v, str) and (BASE64_IMAGE_URI_PATTERN.search(v) or UHID_PATTERN.search(v)):
                raise ValueError("Base64 image data or patient UHID is prohibited in image_assets.")

        img_id = str(item.get("image_id") or "").strip()
        asset_path = str(item.get("asset_path") or "").strip()
        if not img_id and not asset_path:
            continue
        entry: Dict[str, Any] = {
            "image_id": img_id or Path(asset_path).stem,
            "asset_path": asset_path,
            "image_format": str(item.get("image_format") or "png").lower(),
            "file_size": int(item.get("file_size") or 0) if isinstance(item.get("file_size"), (int, float)) else 0,
        }
        if item.get("document_id"):
            entry["document_id"] = str(item["document_id"])
        if item.get("source_document"):
            entry["source_document"] = str(item["source_document"])
        if item.get("page_number") is not None:
            entry["page_number"] = int(item["page_number"])
        clean_list.append(entry)
        image_ids.append(entry["image_id"])

    serialized = json.dumps(clean_list, sort_keys=True, separators=(",", ":"))
    return serialized, ",".join(image_ids), len(clean_list)


def validate_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Union[str, int, float, bool]]:
    """
    Validate and sanitize a metadata dictionary for ChromaDB compatibility and clinical safety.

    - Rejects non-dict metadata, prohibited patient-specific keys (`patient_id`, `uhid`, `ews_score`, etc.),
      binary image data (`bytes`/`bytearray`), and base64 image data URIs.
    - Safely serializes whitelisted multimodal reference fields (`image_assets`, `image_ids`) into
      deterministic ChromaDB scalar strings while rejecting arbitrary nested dicts/lists.
    """
    if metadata is None:
        return {"source": "unknown", "category": "general"}
    if not isinstance(metadata, dict):
        raise ValueError(f"Metadata must be a dict, got {type(metadata).__name__}.")

    validated: Dict[str, Union[str, int, float, bool]] = {}
    for key, val in metadata.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Metadata keys must be non-empty strings.")
        key_clean = key.strip()
        key_lower = key_clean.lower()

        if key_lower in PROHIBITED_PATIENT_METADATA_KEYS:
            raise ValueError(
                f"Prohibited patient-specific metadata field '{key_clean}' cannot be stored in the knowledge base."
            )
        if val is None:
            continue
        if isinstance(val, (bytes, bytearray)):
            raise ValueError(f"Metadata field '{key_clean}' contains binary bytes, which is prohibited.")

        # Handle whitelisted multimodal reference lists (e.g., `image_assets`) safely
        if key_lower == "image_assets":
            assets_json, ids_csv, count = _sanitize_and_serialize_image_assets(val)
            validated["image_assets_json"] = assets_json
            validated["has_images"] = count > 0
            validated["image_count"] = count
            if ids_csv:
                validated["image_ids"] = ids_csv
            continue

        if key_lower in SERIALIZABLE_METADATA_KEYS and isinstance(val, (list, tuple)):
            for item in val:
                if not isinstance(item, (str, int, float, bool)):
                    raise ValueError(
                        f"Metadata field '{key_clean}' contains unsupported nested element of type {type(item).__name__}."
                    )
                if isinstance(item, str) and (UHID_PATTERN.search(item) or BASE64_IMAGE_URI_PATTERN.search(item)):
                    raise ValueError(f"Metadata field '{key_clean}' contains prohibited UHID or base64 data.")
            validated[key_clean] = ",".join(str(x) for x in val)
            continue

        if not isinstance(val, ALLOWED_METADATA_VALUE_TYPES):
            raise ValueError(
                f"Metadata field '{key_clean}' has unsupported type {type(val).__name__}. "
                "ChromaDB metadata values must be str, int, float, or bool."
            )

        if isinstance(val, float) and not math.isfinite(val):
            raise ValueError(f"Metadata field '{key_clean}' contains non-finite float value.")

        if isinstance(val, str):
            if UHID_PATTERN.search(val):
                raise ValueError(
                    f"Metadata field '{key_clean}' contains a patient UHID identifier, which is prohibited."
                )
            if BASE64_IMAGE_URI_PATTERN.search(val):
                raise ValueError(
                    f"Metadata field '{key_clean}' contains base64 image data, which is prohibited."
                )

        validated[key_clean] = val

    if not validated:
        validated["source"] = "unknown"
    return validated


def _enrich_chunk_metadata(
    raw_meta: Optional[Dict[str, Any]],
    chunk_id: str,
    chunk_text: str,
    default_chunk_index: int = 0,
) -> Dict[str, Union[str, int, float, bool]]:
    """
    Ensure every stored chunk metadata dictionary has complete source and version traceability fields:
    - `chunk_id`
    - `document_id`
    - `document_version`
    - `source`
    - `category`
    - `file_type`
    - `page_number` (when available)
    - `chunk_index`
    - `content_hash`
    """
    base = validate_metadata(raw_meta)

    source = str(base.get("source") or "knowledge_base").strip() or "knowledge_base"
    category = str(base.get("category") or "general").strip() or "general"
    file_type = str(base.get("file_type") or _infer_file_type_from_source(source)).strip().lower()

    page_num = base.get("page_number")
    valid_page: Optional[int] = None
    if isinstance(page_num, int) and not isinstance(page_num, bool) and page_num >= 1:
        valid_page = page_num

    document_id = str(
        base.get("document_id") or _derive_document_id_from_source(source, valid_page)
    ).strip()

    inferred_version: Optional[str] = None
    raw_ver = base.get("document_version") or base.get("version")
    if isinstance(raw_ver, (str, int, float)) and not isinstance(raw_ver, bool) and str(raw_ver).strip():
        inferred_version = str(raw_ver).strip()
    elif document_id and chunk_id.startswith(f"{document_id}_v"):
        # Extract version encoded in deterministic chunk_id `<document_id>_v<version>_c<index>_<hash>`
        suffix = chunk_id[len(document_id) + 2:]
        m_ver = re.match(r"^([A-Za-z0-9_.-]+)_c\d+_[0-9a-f]{10}$", suffix)
        if m_ver:
            inferred_version = m_ver.group(1)

    document_version = inferred_version or DEFAULT_DOCUMENT_VERSION

    chunk_index_raw = base.get("chunk_index", default_chunk_index)
    chunk_index = int(chunk_index_raw) if isinstance(chunk_index_raw, (int, float)) and not isinstance(chunk_index_raw, bool) else default_chunk_index

    content_hash = str(base.get("content_hash") or _compute_text_hash(chunk_text)).strip()

    base["chunk_id"] = chunk_id
    base["document_id"] = document_id
    base["document_version"] = document_version
    base["source"] = source
    base["category"] = category
    base["file_type"] = file_type
    base["chunk_index"] = chunk_index
    base["content_hash"] = content_hash
    if valid_page is not None:
        base["page_number"] = valid_page

    return base


def _validate_non_patient_document(text: str) -> str:
    """Validate document text is non-empty and does not contain identifiable patient UHID records or base64 blobs."""
    if not isinstance(text, str):
        raise ValueError(f"Document text must be a str, got {type(text).__name__}.")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Document text must be a non-empty, non-whitespace string.")
    if UHID_PATTERN.search(cleaned):
        raise ValueError(
            "Document text contains a patient UHID identifier. Patient records must not be stored in ChromaDB."
        )
    if BASE64_IMAGE_URI_PATTERN.search(cleaned):
        raise ValueError(
            "Document text contains raw base64 image data. Only image asset file references may be stored."
        )
    return cleaned


def _format_retrieved_record(
    doc_id: str,
    doc_text: str,
    meta: Optional[Dict[str, Any]],
    distance: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Format a retrieved ChromaDB item with top-level citation traceability fields
    (`id`, `chunk_id`, `document_id`, `document_version`, `source`, `category`,
    `file_type`, `page_number`, `chunk_index`, `content_hash`, `image_assets`, `metadata`).
    """
    safe_meta = dict(meta or {})
    image_assets: List[Dict[str, Any]] = []
    raw_assets_json = safe_meta.get("image_assets_json")
    if isinstance(raw_assets_json, str) and raw_assets_json.strip():
        try:
            parsed = json.loads(raw_assets_json)
            if isinstance(parsed, list):
                image_assets = parsed
        except Exception:
            image_assets = []

    record: Dict[str, Any] = {
        "id": doc_id,
        "chunk_id": str(safe_meta.get("chunk_id") or doc_id),
        "document": doc_text,
        "content": doc_text,
        "document_id": safe_meta.get("document_id"),
        "document_version": safe_meta.get("document_version", DEFAULT_DOCUMENT_VERSION),
        "source": safe_meta.get("source", "knowledge_base"),
        "category": safe_meta.get("category", "general"),
        "file_type": safe_meta.get("file_type", "txt"),
        "page_number": safe_meta.get("page_number"),
        "chunk_index": safe_meta.get("chunk_index", 0),
        "content_hash": safe_meta.get("content_hash"),
        "image_assets": image_assets,
        "metadata": safe_meta,
    }
    if distance is not None:
        record["distance"] = float(distance)
    return record


def _sync_chunks_to_mysql_if_available(
    collection_name: str,
    ids: Sequence[str],
    documents: Sequence[str],
    metadatas: Sequence[Dict[str, Any]],
) -> int:
    """
    Synchronize ingested RAG document, image, and chunk metadata references with MySQL
    tables (`rag_documents`, `rag_document_images`, `rag_document_chunks`) created by Migration 009.

    Never stores raw embedding arrays in MySQL. Gracefully degrades if MySQL or the tables
    are unavailable in an offline test environment.
    """
    try:
        from models.chatbot_model import RAGDocument, RAGDocumentChunk, RAGDocumentImage
    except ImportError:
        return 0

    synced_count = 0
    seen_docs: set = set()

    for idx, chunk_id in enumerate(ids):
        try:
            meta = metadatas[idx]
            text = documents[idx]
            doc_id = str(meta.get("document_id") or f"doc_{chunk_id}")
            doc_ver = str(meta.get("document_version") or DEFAULT_DOCUMENT_VERSION)
            source = str(meta.get("source") or "unknown")
            category = str(meta.get("category") or "general")
            file_type = str(meta.get("file_type") or "txt")
            page_num = meta.get("page_number")
            chunk_idx = int(meta.get("chunk_index", idx))
            c_hash = str(meta.get("content_hash") or _compute_text_hash(text))
            ocr_req = bool(meta.get("ocr_required", False))

            doc_key = (doc_id, doc_ver)
            if doc_key not in seen_docs:
                title = Path(source).stem.replace("_", " ").strip().title() or doc_id
                file_name = Path(source).name or f"{doc_id}.{file_type}"
                RAGDocument.upsert(
                    document_id=doc_id,
                    title=title,
                    file_name=file_name,
                    source_path=source,
                    file_type=file_type,
                    content_hash=c_hash,
                    category=category,
                    document_version=doc_ver,
                    page_count=int(page_num) if isinstance(page_num, int) and page_num >= 1 else 1,
                    ocr_required=ocr_req,
                    processing_status="indexed",
                )
                seen_docs.add(doc_key)

            related_image_id: Optional[str] = None
            assets_json = meta.get("image_assets_json")
            if isinstance(assets_json, str) and assets_json.strip():
                try:
                    assets = json.loads(assets_json)
                    if isinstance(assets, list):
                        for img_idx, asset in enumerate(assets, 1):
                            if not isinstance(asset, dict):
                                continue
                            img_id = str(asset.get("image_id") or "").strip()
                            asset_path = str(asset.get("asset_path") or "").strip()
                            if img_id and asset_path:
                                RAGDocumentImage.upsert(
                                    image_id=img_id,
                                    document_id=doc_id,
                                    source_document=source,
                                    asset_path=asset_path,
                                    page_number=page_num if isinstance(page_num, int) else None,
                                    image_index=img_idx,
                                    image_format=str(asset.get("image_format") or "png"),
                                    file_size_bytes=int(asset.get("file_size") or 0),
                                )
                                if related_image_id is None:
                                    related_image_id = img_id
                except Exception as img_exc:
                    logger.debug("Skipped MySQL image metadata sync for chunk '%s': %s", chunk_id, img_exc)

            source_ref = f"{source}#page={page_num}" if page_num is not None else source
            RAGDocumentChunk.upsert(
                chunk_id=chunk_id,
                document_id=doc_id,
                chunk_index=chunk_idx,
                source_reference=source_ref,
                chroma_document_id=chunk_id,
                content_hash=c_hash,
                document_version=doc_ver,
                page_number=page_num if isinstance(page_num, int) else None,
                chroma_collection=collection_name,
                related_image_id=related_image_id,
                char_count=len(text),
                token_count=max(1, len(text.split())),
                processing_status="indexed",
            )
            synced_count += 1
        except Exception as exc:
            logger.debug("MySQL metadata sync skipped/failed for chunk '%s': %s", chunk_id, exc)

    return synced_count


class VectorStore:
    """
    Persistent ChromaDB Vector Store for Jeevan Setu knowledge base documents.
    """

    def __init__(
        self,
        storage_dir: Optional[Union[str, Path]] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        sync_mysql: Optional[bool] = None,
    ):
        if not isinstance(collection_name, str) or not collection_name.strip():
            raise ValueError("collection_name must be a non-empty string.")

        self.storage_dir: Path = get_vector_storage_dir(storage_dir)
        self.collection_name: str = collection_name.strip()
        # By default, sync with MySQL only when operating on the canonical vector storage directory
        if sync_mysql is None:
            self.sync_mysql: bool = (self.storage_dir.resolve() == VECTOR_STORAGE_DIR.resolve())
        else:
            self.sync_mysql = bool(sync_mysql)
        self._client = None
        self._collection = None

    def _get_client(self):
        """Lazily initialize the persistent ChromaDB client with safe error handling."""
        if self._client is None:
            try:
                import chromadb
            except ImportError as exc:
                logger.error("chromadb is not installed: %s", exc)
                raise RuntimeError("The 'chromadb' package is required for VectorStore.") from exc

            try:
                logger.info("Initializing ChromaDB PersistentClient at: %s", self.storage_dir)
                self._client = chromadb.PersistentClient(path=str(self.storage_dir))
            except Exception as exc:
                logger.error("Failed to initialize ChromaDB PersistentClient at '%s': %s", self.storage_dir, exc)
                raise RuntimeError(f"Failed to initialize ChromaDB storage at '{self.storage_dir}': {exc}") from exc
        return self._client

    def get_or_create_collection(self):
        """
        Retrieve the existing ChromaDB collection if it already exists, or create it with
        cosine similarity (`hnsw:space = "cosine"`) and 384-d metadata when it does not exist.
        Never deletes or recreates an existing collection.
        """
        if self._collection is None:
            client = self._get_client()
            try:
                existing_collections = client.list_collections()
                existing_names = {
                    (c.name if hasattr(c, "name") else str(c))
                    for c in existing_collections
                }
                if self.collection_name in existing_names:
                    logger.info("Reusing existing ChromaDB collection: %s", self.collection_name)
                    self._collection = client.get_collection(name=self.collection_name)
                else:
                    logger.info("Creating new ChromaDB collection: %s", self.collection_name)
                    self._collection = client.get_or_create_collection(
                        name=self.collection_name,
                        metadata={
                            "description": "Jeevan Setu Approved Clinical Knowledge Base",
                            "embedding_model": MODEL_NAME,
                            "embedding_dimension": EXPECTED_EMBEDDING_DIMENSION,
                            "hnsw:space": DEFAULT_SIMILARITY_SPACE,
                        },
                    )
            except Exception as exc:
                logger.error("Failed retrieving or creating collection '%s': %s", self.collection_name, exc)
                raise RuntimeError(f"ChromaDB collection initialization failed for '{self.collection_name}': {exc}") from exc
        return self._collection

    def add_chunk(
        self,
        chunk: Union[str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        chunk_id: Optional[str] = None,
        embedding: Optional[Sequence[float]] = None,
        sync_mysql: Optional[bool] = None,
    ) -> str:
        """
        Add or upsert a single document chunk (either a chunk dict from `document_processor.py`
        or a raw text string with optional metadata and chunk_id).

        Returns:
            The stored chunk ID string.
        """
        if isinstance(chunk, dict):
            text = chunk.get("content") or chunk.get("document") or ""
            cid = str(chunk_id or chunk.get("chunk_id") or chunk.get("id") or "").strip()
            merged_meta = dict(chunk.get("metadata") or {})
            if metadata:
                merged_meta.update(metadata)
            for k in (
                "document_id",
                "document_version",
                "version",
                "source",
                "category",
                "file_type",
                "page_number",
                "chunk_index",
                "total_chunks",
                "content_hash",
                "ocr_required",
                "image_assets",
            ):
                if k in chunk and k not in merged_meta and chunk[k] is not None:
                    merged_meta[k] = chunk[k]
            if not cid:
                c_hash = _compute_text_hash(_validate_non_patient_document(text))
                doc_id = str(merged_meta.get("document_id") or "doc")
                doc_ver = str(merged_meta.get("document_version") or DEFAULT_DOCUMENT_VERSION)
                c_idx = int(merged_meta.get("chunk_index", 0))
                cid = f"{doc_id}_v{doc_ver}_c{c_idx}_{c_hash[:10]}"
            embs = [embedding] if embedding is not None else None
            stored_ids = self.add_documents(
                documents=[text],
                metadatas=[merged_meta],
                ids=[cid],
                embeddings=embs,
                sync_mysql=sync_mysql,
            )
            return stored_ids[0]

        if not isinstance(chunk, str):
            raise ValueError(f"chunk must be a str or dict, got {type(chunk).__name__}.")

        ids_arg = [chunk_id] if chunk_id is not None else None
        metas_arg = [metadata] if metadata is not None else None
        embs_arg = [embedding] if embedding is not None else None
        stored_ids = self.add_documents(
            documents=[chunk],
            metadatas=metas_arg,
            ids=ids_arg,
            embeddings=embs_arg,
            sync_mysql=sync_mysql,
        )
        return stored_ids[0]

    def add_documents(
        self,
        documents: Sequence[str],
        metadatas: Optional[Sequence[Dict[str, Any]]] = None,
        ids: Optional[Sequence[str]] = None,
        embeddings: Optional[Sequence[Sequence[float]]] = None,
        sync_mysql: Optional[bool] = None,
    ) -> List[str]:
        """
        Add or upsert document chunks with unique IDs, enriched traceability metadata,
        and validated 384-d embeddings.

        Optimizes idempotent re-ingestion: if a chunk with the same ID and identical
        `content_hash` (or identical text) is already stored in the collection with a valid
        384-d embedding, reuses the existing embedding instead of recomputing it.
        """
        if not isinstance(documents, (list, tuple)) or len(documents) == 0:
            raise ValueError("documents must be a non-empty list or tuple of strings.")

        cleaned_docs = [_validate_non_patient_document(doc) for doc in documents]
        num_docs = len(cleaned_docs)

        if metadatas is not None:
            if not isinstance(metadatas, (list, tuple)) or len(metadatas) != num_docs:
                raise ValueError("metadatas must be a list/tuple with the same length as documents.")
            raw_metas: List[Optional[Dict[str, Any]]] = list(metadatas)
        else:
            raw_metas = [None] * num_docs

        if ids is not None:
            if not isinstance(ids, (list, tuple)) or len(ids) != num_docs:
                raise ValueError("ids must be a list/tuple with the same length as documents.")
            cleaned_ids: List[str] = []
            for idx, item_id in enumerate(ids):
                if not isinstance(item_id, str) or not item_id.strip():
                    raise ValueError(f"ID at index {idx} must be a non-empty string.")
                cleaned_ids.append(item_id.strip())
            if len(set(cleaned_ids)) != num_docs:
                raise ValueError("All document chunk IDs in a batch must be unique.")
        else:
            cleaned_ids = []
            for idx, doc_text in enumerate(cleaned_docs):
                rm = raw_metas[idx] if isinstance(raw_metas[idx], dict) else {}
                c_hash = _compute_text_hash(doc_text)
                doc_id = str((rm or {}).get("document_id") or _derive_document_id_from_source(str((rm or {}).get("source") or "doc")))
                doc_ver = str((rm or {}).get("document_version") or (rm or {}).get("version") or DEFAULT_DOCUMENT_VERSION)
                c_idx = int((rm or {}).get("chunk_index", idx))
                cleaned_ids.append(f"{doc_id}_v{doc_ver}_c{c_idx}_{c_hash[:10]}")

        enriched_metadatas: List[Dict[str, Union[str, int, float, bool]]] = [
            _enrich_chunk_metadata(raw_metas[i], cleaned_ids[i], cleaned_docs[i], default_chunk_index=i)
            for i in range(num_docs)
        ]

        collection = self.get_or_create_collection()

        # Resolve or validate 384-d embeddings
        final_embeddings: List[List[float]] = [[] for _ in range(num_docs)]
        if embeddings is not None:
            if not isinstance(embeddings, (list, tuple)) or len(embeddings) != num_docs:
                raise ValueError("embeddings must be a list/tuple with the same length as documents.")
            for idx, vec in enumerate(embeddings):
                final_embeddings[idx] = validate_embedding_vector(vec, EXPECTED_EMBEDDING_DIMENSION)
        else:
            # Check whether any of these chunk IDs already exist in ChromaDB with unchanged content
            existing_map: Dict[str, Tuple[str, Optional[str], Optional[List[float]]]] = {}
            try:
                if collection.count() > 0:
                    existing_res = collection.get(
                        ids=cleaned_ids,
                        include=["documents", "metadatas", "embeddings"],
                    )
                    ex_ids = existing_res.get("ids") or []
                    ex_docs = existing_res.get("documents") or []
                    ex_metas = existing_res.get("metadatas") or []
                    ex_embs = existing_res.get("embeddings")
                    if ex_embs is None:
                        ex_embs = []
                    for e_i, e_id in enumerate(ex_ids):
                        e_doc = ex_docs[e_i] if e_i < len(ex_docs) else ""
                        e_meta = ex_metas[e_i] if e_i < len(ex_metas) and ex_metas[e_i] else {}
                        e_hash = e_meta.get("content_hash")
                        e_emb_raw = ex_embs[e_i] if e_i < len(ex_embs) else None
                        e_emb_list: Optional[List[float]] = None
                        if e_emb_raw is not None:
                            vals = e_emb_raw.tolist() if hasattr(e_emb_raw, "tolist") else list(e_emb_raw)
                            if len(vals) == EXPECTED_EMBEDDING_DIMENSION:
                                e_emb_list = [float(x) for x in vals]
                        existing_map[e_id] = (e_doc, e_hash, e_emb_list)
            except Exception as exc:
                logger.debug("Existing chunk lookup skipped prior to batch embedding: %s", exc)

            texts_to_encode: List[str] = []
            indices_to_encode: List[int] = []

            for i in range(num_docs):
                cid = cleaned_ids[i]
                new_text = cleaned_docs[i]
                new_hash = str(enriched_metadatas[i]["content_hash"])
                if cid in existing_map:
                    old_doc, old_hash, old_emb = existing_map[cid]
                    if old_emb is not None and (old_hash == new_hash or old_doc == new_text):
                        final_embeddings[i] = validate_embedding_vector(old_emb, EXPECTED_EMBEDDING_DIMENSION)
                        continue
                texts_to_encode.append(new_text)
                indices_to_encode.append(i)

            if len(texts_to_encode) == 1:
                single_vec = validate_embedding_vector(
                    get_embedding(texts_to_encode[0]),
                    EXPECTED_EMBEDDING_DIMENSION,
                )
                final_embeddings[indices_to_encode[0]] = single_vec
            elif len(texts_to_encode) > 1:
                computed_vecs = get_embeddings(texts_to_encode)
                for batch_pos, doc_idx in enumerate(indices_to_encode):
                    final_embeddings[doc_idx] = validate_embedding_vector(
                        computed_vecs[batch_pos],
                        EXPECTED_EMBEDDING_DIMENSION,
                    )

        logger.info("Storing %d document chunks into collection '%s'", num_docs, self.collection_name)
        collection.upsert(
            ids=cleaned_ids,
            documents=cleaned_docs,
            embeddings=final_embeddings,
            metadatas=enriched_metadatas,
        )

        should_sync_mysql = self.sync_mysql if sync_mysql is None else bool(sync_mysql)
        if should_sync_mysql:
            _sync_chunks_to_mysql_if_available(
                collection_name=self.collection_name,
                ids=cleaned_ids,
                documents=cleaned_docs,
                metadatas=enriched_metadatas,
            )

        return cleaned_ids

    def add_chunks(
        self,
        chunks: Sequence[Dict[str, Any]],
        sync_mysql: Optional[bool] = None,
    ) -> List[str]:
        """
        Add a batch of structured chunk dicts (such as output from `document_processor.process_documents()`).
        Preserves stable `chunk_id`, `document_id`, `document_version`, `source`, `category`,
        `file_type`, `page_number`, `chunk_index`, `content_hash`, and `image_assets`.
        """
        if not isinstance(chunks, (list, tuple)) or len(chunks) == 0:
            raise ValueError("chunks must be a non-empty list of chunk dictionaries.")

        docs: List[str] = []
        ids: List[str] = []
        metas: List[Dict[str, Any]] = []
        provided_embeddings: List[Sequence[float]] = []
        has_all_embeddings = True

        seen_batch_ids: set = set()
        dedup_docs: List[str] = []
        dedup_ids: List[str] = []
        dedup_metas: List[Dict[str, Any]] = []
        dedup_embs: List[Sequence[float]] = []

        for idx, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                raise ValueError(f"Chunk at index {idx} must be a dict.")
            text = chunk.get("content") or chunk.get("document") or ""
            cleaned_text = _validate_non_patient_document(text)

            meta = dict(chunk.get("metadata") or {})
            for k in (
                "document_id",
                "document_version",
                "version",
                "source",
                "category",
                "file_type",
                "page_number",
                "chunk_index",
                "total_chunks",
                "content_hash",
                "ocr_required",
                "image_assets",
            ):
                if k in chunk and k not in meta and chunk[k] is not None:
                    meta[k] = chunk[k]

            raw_cid = chunk.get("chunk_id") or chunk.get("id")
            if isinstance(raw_cid, str) and raw_cid.strip():
                chunk_id = raw_cid.strip()
            else:
                c_hash = _compute_text_hash(cleaned_text)
                doc_id = str(meta.get("document_id") or _derive_document_id_from_source(str(meta.get("source") or "doc")))
                doc_ver = str(meta.get("document_version") or meta.get("version") or DEFAULT_DOCUMENT_VERSION)
                c_idx = int(meta.get("chunk_index", idx))
                chunk_id = f"{doc_id}_v{doc_ver}_c{c_idx}_{c_hash[:10]}"

            # If the same chunk_id appears twice in the same batch with identical content, deduplicate it
            if chunk_id in seen_batch_ids:
                continue
            seen_batch_ids.add(chunk_id)

            dedup_docs.append(cleaned_text)
            dedup_ids.append(chunk_id)
            dedup_metas.append(meta)

            if "embedding" in chunk and chunk["embedding"] is not None:
                dedup_embs.append(chunk["embedding"])
            else:
                has_all_embeddings = False

        return self.add_documents(
            documents=dedup_docs,
            metadatas=dedup_metas,
            ids=dedup_ids,
            embeddings=dedup_embs if (has_all_embeddings and len(dedup_embs) == len(dedup_docs)) else None,
            sync_mysql=sync_mysql,
        )

    def get_chunks_by_ids(self, ids: Sequence[str]) -> List[Dict[str, Any]]:
        """
        Retrieve stored document chunks by their IDs in the requested order.

        Args:
            ids: Non-empty sequence of chunk IDs to fetch.

        Returns:
            List of formatted chunk records (with full source/version traceability).
        """
        if not isinstance(ids, (list, tuple)) or len(ids) == 0:
            raise ValueError("ids must be a non-empty list or tuple of chunk IDs.")

        cleaned_ids: List[str] = []
        for idx, item_id in enumerate(ids):
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError(f"ID at index {idx} must be a non-empty string.")
            cleaned_ids.append(item_id.strip())

        collection = self.get_or_create_collection()
        if collection.count() == 0:
            return []

        raw = collection.get(ids=cleaned_ids, include=["documents", "metadatas"])
        returned_ids = raw.get("ids") or []
        returned_docs = raw.get("documents") or []
        returned_metas = raw.get("metadatas") or []

        by_id: Dict[str, Dict[str, Any]] = {}
        for idx, cid in enumerate(returned_ids):
            doc_text = returned_docs[idx] if idx < len(returned_docs) else ""
            meta = returned_metas[idx] if idx < len(returned_metas) and returned_metas[idx] is not None else {}
            by_id[cid] = _format_retrieved_record(cid, doc_text, meta)

        return [by_id[cid] for cid in cleaned_ids if cid in by_id]

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic similarity search using the 384-d query embedding.

        Args:
            query: Non-empty search query string.
            top_k: Maximum number of results to return.
            where: Optional ChromaDB metadata filter dictionary.

        Returns:
            List of dicts containing `id`, `chunk_id`, `document`, `content`, `document_id`,
            `document_version`, `source`, `category`, `file_type`, `page_number`, `chunk_index`,
            `image_assets`, `metadata`, and `distance`.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query must be a non-empty string.")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise ValueError("top_k must be a positive integer.")

        collection = self.get_or_create_collection()
        total_count = collection.count()
        if total_count == 0:
            return []

        n_results = min(top_k, total_count)
        query_embedding = validate_embedding_vector(
            get_embedding(query.strip()),
            EXPECTED_EMBEDDING_DIMENSION,
        )

        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        raw = collection.query(**query_kwargs)
        ids_list = (raw.get("ids") or [[]])[0]
        docs_list = (raw.get("documents") or [[]])[0]
        metas_list = (raw.get("metadatas") or [[]])[0]
        dists_list = (raw.get("distances") or [[]])[0]

        results: List[Dict[str, Any]] = []
        for idx, doc_id in enumerate(ids_list):
            doc_text = docs_list[idx] if idx < len(docs_list) else ""
            meta = metas_list[idx] if idx < len(metas_list) and metas_list[idx] is not None else {}
            dist = float(dists_list[idx]) if idx < len(dists_list) and dists_list[idx] is not None else 0.0
            results.append(_format_retrieved_record(doc_id, doc_text, meta, distance=dist))
        return results

    def update_documents(
        self,
        ids: Sequence[str],
        documents: Optional[Sequence[str]] = None,
        metadatas: Optional[Sequence[Dict[str, Any]]] = None,
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> List[str]:
        """
        Update existing document chunks in-place by ID without creating duplicates.
        """
        if not isinstance(ids, (list, tuple)) or len(ids) == 0:
            raise ValueError("ids must be a non-empty list/tuple of chunk IDs.")
        if documents is None and metadatas is None and embeddings is None:
            raise ValueError("At least one of 'documents', 'metadatas', or 'embeddings' must be provided for update.")

        cleaned_ids = []
        for idx, item_id in enumerate(ids):
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError(f"ID at index {idx} must be a non-empty string.")
            cleaned_ids.append(item_id.strip())

        update_kwargs: Dict[str, Any] = {"ids": cleaned_ids}

        cleaned_docs: Optional[List[str]] = None
        if documents is not None:
            if not isinstance(documents, (list, tuple)) or len(documents) != len(cleaned_ids):
                raise ValueError("documents must have the same length as ids.")
            cleaned_docs = [_validate_non_patient_document(d) for d in documents]
            update_kwargs["documents"] = cleaned_docs

        if embeddings is not None:
            if not isinstance(embeddings, (list, tuple)) or len(embeddings) != len(cleaned_ids):
                raise ValueError("embeddings must have the same length as ids.")
            update_kwargs["embeddings"] = [
                validate_embedding_vector(v, EXPECTED_EMBEDDING_DIMENSION) for v in embeddings
            ]
        elif cleaned_docs is not None:
            computed = get_embeddings(cleaned_docs) if len(cleaned_docs) > 1 else [get_embedding(cleaned_docs[0])]
            update_kwargs["embeddings"] = [
                validate_embedding_vector(v, EXPECTED_EMBEDDING_DIMENSION) for v in computed
            ]

        if metadatas is not None:
            if not isinstance(metadatas, (list, tuple)) or len(metadatas) != len(cleaned_ids):
                raise ValueError("metadatas must have the same length as ids.")
            enriched_metas = []
            for idx, m in enumerate(metadatas):
                doc_for_hash = cleaned_docs[idx] if cleaned_docs is not None else ""
                enriched = _enrich_chunk_metadata(m, cleaned_ids[idx], doc_for_hash, default_chunk_index=idx)
                enriched_metas.append(enriched)
            update_kwargs["metadatas"] = enriched_metas

        collection = self.get_or_create_collection()
        logger.info("Updating %d chunks in collection '%s'", len(cleaned_ids), self.collection_name)
        collection.update(**update_kwargs)
        return cleaned_ids

    def delete_documents(self, ids: Sequence[str]) -> List[str]:
        """
        Delete selected document chunks by ID without affecting any other documents.
        """
        if not isinstance(ids, (list, tuple)) or len(ids) == 0:
            raise ValueError("ids must be a non-empty list/tuple of chunk IDs to delete.")

        cleaned_ids = []
        for idx, item_id in enumerate(ids):
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError(f"ID at index {idx} must be a non-empty string.")
            cleaned_ids.append(item_id.strip())

        collection = self.get_or_create_collection()
        logger.info("Deleting %d chunks from collection '%s'", len(cleaned_ids), self.collection_name)
        collection.delete(ids=cleaned_ids)
        return cleaned_ids

    def delete_chunks_by_document(
        self,
        document_id: str,
        document_version: Optional[str] = None,
    ) -> List[str]:
        """
        Safely remove chunks belonging only to a specific `document_id` (and optionally a specific
        `document_version`) without touching chunks belonging to any other documents or versions.
        """
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id must be a non-empty string.")

        doc_id_clean = document_id.strip()
        all_items = self.get_all()
        matching_ids: List[str] = []
        for item in all_items:
            meta = item.get("metadata") or {}
            if meta.get("document_id") != doc_id_clean:
                continue
            if document_version is not None and str(meta.get("document_version")) != str(document_version).strip():
                continue
            matching_ids.append(item["id"])

        if matching_ids:
            self.delete_documents(matching_ids)
        return matching_ids

    def get_collection_count(self) -> int:
        """Return total number of document chunks stored in the collection."""
        collection = self.get_or_create_collection()
        return int(collection.count())

    def get_collection_info(self) -> Dict[str, Any]:
        """Return diagnostic and configuration metadata about the ChromaDB collection."""
        collection = self.get_or_create_collection()
        col_meta = dict(collection.metadata or {})
        return {
            "name": collection.name,
            "count": int(collection.count()),
            "storage_dir": str(self.storage_dir),
            "embedding_model": MODEL_NAME,
            "embedding_dimension": EXPECTED_EMBEDDING_DIMENSION,
            "similarity_metric": col_meta.get("hnsw:space", DEFAULT_SIMILARITY_SPACE),
            "metadata": col_meta,
        }

    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all stored chunks in the collection with full citation metadata."""
        collection = self.get_or_create_collection()
        if collection.count() == 0:
            return []
        raw = collection.get(include=["documents", "metadatas"])
        ids_list = raw.get("ids") or []
        docs_list = raw.get("documents") or []
        metas_list = raw.get("metadatas") or []

        items: List[Dict[str, Any]] = []
        for idx, doc_id in enumerate(ids_list):
            doc_text = docs_list[idx] if idx < len(docs_list) else ""
            meta = metas_list[idx] if idx < len(metas_list) and metas_list[idx] is not None else {}
            items.append(_format_retrieved_record(doc_id, doc_text, meta))
        return items


# ---------------------------------------------------------------------------
# Module-level functional interface
# ---------------------------------------------------------------------------

def init_vector_store(
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    sync_mysql: Optional[bool] = None,
) -> VectorStore:
    """Initialize and return a persistent ChromaDB VectorStore instance."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name, sync_mysql=sync_mysql)
    store.get_or_create_collection()
    return store


def get_or_create_collection(
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
):
    """Create or retrieve the configured ChromaDB collection."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name)
    return store.get_or_create_collection()


def add_document_chunk(
    chunk: Union[str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    chunk_id: Optional[str] = None,
    embedding: Optional[Sequence[float]] = None,
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    sync_mysql: Optional[bool] = None,
) -> str:
    """Add a single document chunk (text or processor chunk dict) to ChromaDB."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name, sync_mysql=sync_mysql)
    return store.add_chunk(chunk=chunk, metadata=metadata, chunk_id=chunk_id, embedding=embedding, sync_mysql=sync_mysql)


def add_document_chunks(
    documents: Sequence[Union[str, Dict[str, Any]]],
    metadatas: Optional[Sequence[Dict[str, Any]]] = None,
    ids: Optional[Sequence[str]] = None,
    embeddings: Optional[Sequence[Sequence[float]]] = None,
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    sync_mysql: Optional[bool] = None,
) -> List[str]:
    """
    Add multiple document chunks to ChromaDB.
    Accepts either a sequence of strings (with optional `metadatas`, `ids`, `embeddings`)
    or a sequence of structured chunk dicts from `document_processor.process_documents()`.
    """
    if not isinstance(documents, (list, tuple)) or len(documents) == 0:
        raise ValueError("documents must be a non-empty list or tuple.")
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name, sync_mysql=sync_mysql)
    if isinstance(documents[0], dict):
        return store.add_chunks(chunks=documents, sync_mysql=sync_mysql)  # type: ignore[arg-type]
    return store.add_documents(
        documents=documents,  # type: ignore[arg-type]
        metadatas=metadatas,
        ids=ids,
        embeddings=embeddings,
        sync_mysql=sync_mysql,
    )


def get_chunks_by_ids(
    ids: Sequence[str],
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> List[Dict[str, Any]]:
    """Retrieve stored document chunks by their IDs."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name)
    return store.get_chunks_by_ids(ids=ids)


def search_similar_chunks(
    query: str,
    top_k: int = 5,
    where: Optional[Dict[str, Any]] = None,
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> List[Dict[str, Any]]:
    """Search ChromaDB collection using semantic query embeddings."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name)
    return store.search(query=query, top_k=top_k, where=where)


def update_document_chunks(
    ids: Sequence[str],
    documents: Optional[Sequence[str]] = None,
    metadatas: Optional[Sequence[Dict[str, Any]]] = None,
    embeddings: Optional[Sequence[Sequence[float]]] = None,
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> List[str]:
    """Update existing document chunks in-place without creating duplicates."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name)
    return store.update_documents(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)


def delete_document_chunks(
    ids: Sequence[str],
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> List[str]:
    """Delete selected document chunks by ID from ChromaDB."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name)
    return store.delete_documents(ids=ids)


def get_collection_count(
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> int:
    """Return the total number of chunks in the ChromaDB collection."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name)
    return store.get_collection_count()


def get_collection_info(
    storage_dir: Optional[Union[str, Path]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> Dict[str, Any]:
    """Return metadata and configuration details for the ChromaDB collection."""
    store = VectorStore(storage_dir=storage_dir, collection_name=collection_name)
    return store.get_collection_info()
