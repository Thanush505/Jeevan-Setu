"""
chatbot/rag/document_loader.py — Multi-Format Knowledge Base Document & Asset Loader for Jeevan Setu RAG.

Supports safe ingestion of approved knowledge-base documents:
- PDF (`.pdf`) — page-by-page extraction with page numbers, scanned-page OCR flagging, and embedded image extraction
- DOCX (`.docx`) — ordered paragraph & table extraction plus embedded image extraction
- TXT (`.txt`) — UTF-8 text extraction
- Markdown (`.md`, `.markdown`) — UTF-8 markdown extraction
- JSON (`.json`) — validated structured JSON-to-readable-text conversion

Strictly resolves paths within `JEEVAN_SETU/knowledge_base/` (or a provided `base_dir`),
extracts embedded images into a dedicated asset directory outside ChromaDB, and enforces
size, count, and clinical privacy guardrails.
"""

import hashlib
import json
import logging
import re
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("jeevan_setu.rag.document_loader")

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_BASE_DIR = BACKEND_ROOT / "knowledge_base"
EXTRACTED_ASSETS_DIR_NAME = "_extracted_assets"

KNOWLEDGE_SUBFOLDERS = (
    "clinical_protocols",
    "hospital_sops",
    "project_documentation",
    "approved_guidelines",
)

SUPPORTED_EXTENSIONS: Dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
}

# Security & resource limits
DEFAULT_MAX_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
DEFAULT_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024     # 10 MB
DEFAULT_MAX_IMAGES_PER_DOCUMENT = 50

BLOCKED_FILENAMES: Set[str] = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.json",
    "service_account.json",
    "package-lock.json",
    "tsconfig.json",
    "pyrightconfig.json",
}
BLOCKED_EXTENSIONS: Set[str] = {
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".sql",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".tmp",
    ".bak",
    ".swp",
    ".exe",
    ".dll",
    ".bat",
    ".ps1",
    ".sh",
}

# Guardrail against ingesting identifiable patient records into the shared knowledge base
UHID_PATTERN = re.compile(r"\bUHID-\d{4}-\d{5}\b", re.IGNORECASE)


def get_knowledge_base_dir() -> Path:
    """Return the canonical JEEVAN_SETU/knowledge_base directory path."""
    return KNOWLEDGE_BASE_DIR


def get_knowledge_base_assets_dir(base_dir: Optional[Union[str, Path]] = None) -> Path:
    """Return the dedicated directory for extracted document image assets."""
    root = Path(base_dir).resolve() if base_dir else KNOWLEDGE_BASE_DIR.resolve()
    return root / EXTRACTED_ASSETS_DIR_NAME


def _compute_stable_document_id(rel_source: str, page_number: Optional[int] = None) -> str:
    """
    Generate a deterministic, collision-resistant document ID from relative source path and page number.
    """
    normalized_source = rel_source.replace("\\", "/")
    key = f"{normalized_source}#p{page_number}" if page_number is not None else normalized_source
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(normalized_source).stem).strip("_").lower() or "doc"
    if page_number is not None:
        return f"doc_{stem}_p{page_number}_{digest}"
    return f"doc_{stem}_{digest}"


def _is_hidden_or_ignored_path(path: Path, root: Path) -> bool:
    """
    Determine whether a file or any of its relative parent directories is hidden,
    temporary, or inside the extracted assets directory.
    """
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True

    for part in rel_parts:
        if part.startswith(".") or part.startswith("~$") or part == EXTRACTED_ASSETS_DIR_NAME:
            return True
    name_lower = path.name.lower()
    if name_lower in BLOCKED_FILENAMES or name_lower.endswith("~"):
        return True
    if path.suffix.lower() in BLOCKED_EXTENSIONS:
        return True
    return False


def _is_safe_subpath(path: Path, root: Path) -> bool:
    """Ensure resolved path stays strictly inside the resolved knowledge-base root."""
    try:
        resolved_root = root.resolve()
        resolved_path = path.resolve()
        return resolved_path.is_relative_to(resolved_root)
    except Exception:
        return False


def _detect_image_format(data: bytes) -> Optional[str]:
    """
    Validate image header/magic bytes and return canonical extension ('png', 'jpg', 'gif', 'bmp', 'webp', 'tiff', 'jp2').
    Returns None if data is empty, truncated, or not a recognized image format.
    """
    if not data or len(data) < 12:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in data[-32:]:
        return "png"
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "jpg"
    if data.startswith(b"\xff\xd8\xff") and len(data) >= 32:
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"BM") and len(data) >= 26:
        return "bmp"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if data.startswith(b"\x00\x00\x00\x0cjP  \r\n\x87\n"):
        return "jp2"
    return None


def _encode_raw_pixels_to_png(raw_bytes: bytes, width: int, height: int, channels: int) -> Optional[bytes]:
    """
    Convert raw 8-bit grayscale (1 channel) or RGB (3 channels) pixel buffer from a PDF FlateDecode
    Image XObject into a valid standard PNG byte stream using pure Python stdlib (`struct` + `zlib`).
    """
    if width <= 0 or height <= 0 or channels not in (1, 3):
        return None
    expected_len = width * height * channels
    if len(raw_bytes) < expected_len:
        return None

    color_type = 0 if channels == 1 else 2  # 0 = Grayscale, 2 = Truecolor RGB
    row_bytes = width * channels
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)  # Filter type 0 (None)
        offset = y * row_bytes
        scanlines.extend(raw_bytes[offset : offset + row_bytes])

    def _make_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        return struct.pack(">I", len(chunk_data)) + chunk_type + chunk_data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    compressed = zlib.compress(bytes(scanlines), level=6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _make_chunk(b"IHDR", ihdr)
        + _make_chunk(b"IDAT", compressed)
        + _make_chunk(b"IEND", b"")
    )


def _save_extracted_image(
    image_bytes: bytes,
    rel_source: str,
    document_id: str,
    image_index: int,
    assets_dir: Path,
    root_dir: Path,
    page_number: Optional[int],
    max_image_size_bytes: int,
) -> Optional[Dict[str, Any]]:
    """
    Validate and persist an extracted image asset to `assets_dir` with deterministic naming.
    Returns metadata dictionary or None if invalid/oversized.
    """
    if not image_bytes:
        return None
    size = len(image_bytes)
    if size > max_image_size_bytes:
        logger.warning(
            "Skipping oversized embedded image (%d bytes > %d limit) in '%s' (page=%s)",
            size,
            max_image_size_bytes,
            rel_source,
            page_number,
        )
        return None

    img_format = _detect_image_format(image_bytes)
    if not img_format:
        logger.warning(
            "Skipping corrupt or unsupported embedded image in '%s' (page=%s, index=%d)",
            rel_source,
            page_number,
            image_index,
        )
        return None

    digest = hashlib.sha256(image_bytes).hexdigest()[:10]
    safe_stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(rel_source).stem).strip("_").lower() or "doc"
    if page_number is not None:
        filename = f"{safe_stem}_p{page_number}_img{image_index}_{digest}.{img_format}"
    else:
        filename = f"{safe_stem}_img{image_index}_{digest}.{img_format}"

    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
        target_path = (assets_dir / filename).resolve()
        if not target_path.is_relative_to(assets_dir.resolve()):
            logger.warning("Blocked unsafe asset write path for '%s'", filename)
            return None

        if not target_path.exists():
            target_path.write_bytes(image_bytes)

        try:
            rel_asset_path = str(target_path.relative_to(root_dir.resolve())).replace("\\", "/")
        except ValueError:
            rel_asset_path = f"{EXTRACTED_ASSETS_DIR_NAME}/{filename}"

        image_id = f"img_{safe_stem}_{f'p{page_number}_' if page_number is not None else ''}{image_index}_{digest}"
        return {
            "image_id": image_id,
            "source_document": rel_source.replace("\\", "/"),
            "document_id": document_id,
            "page_number": page_number,
            "image_format": img_format,
            "file_size": size,
            "asset_path": rel_asset_path,
        }
    except Exception as exc:
        logger.warning("Failed saving extracted image for '%s': %s", rel_source, exc)
        return None


def _extract_pdf_page_images(
    page: Any,
    rel_source: str,
    document_id: str,
    page_number: int,
    assets_dir: Path,
    root_dir: Path,
    max_image_size_bytes: int,
    remaining_image_quota: int,
) -> List[Dict[str, Any]]:
    """
    Extract embedded images from a single pypdf PageObject.
    Uses `page.images` when Pillow is installed, and falls back to direct PDF `/Resources -> /XObject`
    stream extraction when Pillow is absent or when an individual image fails decoding.
    """
    extracted: List[Dict[str, Any]] = []
    if remaining_image_quota <= 0:
        return extracted

    seen_hashes: Set[str] = set()
    img_counter = 0

    # 1. Try pypdf's high-level `page.images` API first (if Pillow is available)
    used_high_level = False
    try:
        page_images = page.images
        num_imgs = len(page_images)
        used_high_level = True
        for i in range(num_imgs):
            if len(extracted) >= remaining_image_quota:
                logger.warning("Reached max_images_per_document limit for '%s'", rel_source)
                break
            try:
                img_obj = page_images[i]
                raw_data = getattr(img_obj, "data", None)
                if not raw_data:
                    continue
                digest = hashlib.sha256(raw_data).hexdigest()
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)
                img_counter += 1
                meta = _save_extracted_image(
                    image_bytes=raw_data,
                    rel_source=rel_source,
                    document_id=document_id,
                    image_index=img_counter,
                    assets_dir=assets_dir,
                    root_dir=root_dir,
                    page_number=page_number,
                    max_image_size_bytes=max_image_size_bytes,
                )
                if meta:
                    extracted.append(meta)
            except ImportError:
                used_high_level = False
                break
            except Exception as exc:
                logger.warning(
                    "Skipping unreadable PDF image on page %d of '%s': %s",
                    page_number,
                    rel_source,
                    exc,
                )
    except ImportError:
        used_high_level = False
    except Exception as exc:
        logger.debug("High-level page.images inspection fell back on page %d of '%s': %s", page_number, rel_source, exc)

    # 2. Direct XObject fallback (works even without Pillow installed)
    if not used_high_level and len(extracted) < remaining_image_quota:
        try:
            resources = page.get("/Resources")
            if resources is not None:
                resources_obj = resources.get_object() if hasattr(resources, "get_object") else resources
                xobjects = resources_obj.get("/XObject") if isinstance(resources_obj, dict) else None
                if xobjects is not None:
                    xobjects_dict = xobjects.get_object() if hasattr(xobjects, "get_object") else xobjects
                    if isinstance(xobjects_dict, dict):
                        for xobj_name, xobj_ref in xobjects_dict.items():
                            if len(extracted) >= remaining_image_quota:
                                logger.warning("Reached max_images_per_document limit for '%s'", rel_source)
                                break
                            try:
                                xobj = xobj_ref.get_object() if hasattr(xobj_ref, "get_object") else xobj_ref
                                subtype = xobj.get("/Subtype") if isinstance(xobj, dict) else None
                                if subtype != "/Image":
                                    continue

                                raw_bytes: Optional[bytes] = None
                                filt = xobj.get("/Filter")
                                if hasattr(filt, "get_object"):
                                    filt = filt.get_object()
                                filt_str = str(filt) if filt is not None else ""

                                if "/DCTDecode" in filt_str or "/JPXDecode" in filt_str:
                                    raw_bytes = getattr(xobj, "_data", None) or xobj.get_data()
                                else:
                                    stream_data = xobj.get_data()
                                    if _detect_image_format(stream_data):
                                        raw_bytes = stream_data
                                    else:
                                        width = int(xobj.get("/Width", 0) or 0)
                                        height = int(xobj.get("/Height", 0) or 0)
                                        cs = str(xobj.get("/ColorSpace", "/DeviceRGB"))
                                        channels = 1 if "Gray" in cs else 3
                                        raw_bytes = _encode_raw_pixels_to_png(stream_data, width, height, channels)

                                if not raw_bytes:
                                    logger.warning(
                                        "Skipping corrupt or unsupported PDF XObject image '%s' on page %d of '%s'",
                                        xobj_name,
                                        page_number,
                                        rel_source,
                                    )
                                    continue

                                digest = hashlib.sha256(raw_bytes).hexdigest()
                                if digest in seen_hashes:
                                    continue
                                seen_hashes.add(digest)
                                img_counter += 1
                                meta = _save_extracted_image(
                                    image_bytes=raw_bytes,
                                    rel_source=rel_source,
                                    document_id=document_id,
                                    image_index=img_counter,
                                    assets_dir=assets_dir,
                                    root_dir=root_dir,
                                    page_number=page_number,
                                    max_image_size_bytes=max_image_size_bytes,
                                )
                                if meta:
                                    extracted.append(meta)
                            except Exception as exc:
                                logger.warning(
                                    "Failed extracting XObject image '%s' on page %d of '%s': %s",
                                    xobj_name,
                                    page_number,
                                    rel_source,
                                    exc,
                                )
        except Exception as exc:
            logger.warning("Failed inspecting PDF XObject resources on page %d of '%s': %s", page_number, rel_source, exc)

    return extracted


def _load_pdf_document(
    path: Path,
    rel_source: str,
    category: str,
    assets_dir: Path,
    root_dir: Path,
    max_image_size_bytes: int,
    max_images_per_document: int,
) -> List[Dict[str, Any]]:
    """
    Extract page-level document records and embedded images from a PDF file.
    """
    try:
        import pypdf
    except ImportError as exc:
        logger.error("pypdf is not installed; cannot load PDF '%s': %s", rel_source, exc)
        return []

    records: List[Dict[str, Any]] = []
    try:
        reader = pypdf.PdfReader(str(path), strict=False)
        total_pages = len(reader.pages)
    except Exception as exc:
        logger.warning("Skipping corrupt or unreadable PDF '%s': %s", rel_source, exc)
        return []

    total_images_extracted = 0
    for idx in range(total_pages):
        page_number = idx + 1
        doc_id = _compute_stable_document_id(rel_source, page_number=page_number)
        try:
            page = reader.pages[idx]
            raw_text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("Failed extracting text from page %d of PDF '%s': %s", page_number, rel_source, exc)
            raw_text = ""

        cleaned_text = raw_text.strip()
        if UHID_PATTERN.search(cleaned_text):
            logger.warning("Skipping PDF page %d in '%s': contains patient UHID record.", page_number, rel_source)
            continue

        remaining_quota = max(0, max_images_per_document - total_images_extracted)
        page_images = _extract_pdf_page_images(
            page=page,
            rel_source=rel_source,
            document_id=doc_id,
            page_number=page_number,
            assets_dir=assets_dir,
            root_dir=root_dir,
            max_image_size_bytes=max_image_size_bytes,
            remaining_image_quota=remaining_quota,
        )
        total_images_extracted += len(page_images)

        ocr_required = False
        if not cleaned_text:
            ocr_required = True
            cleaned_text = (
                f"[Scanned or image-only PDF page {page_number} in {rel_source.replace(chr(92), '/')}; "
                "no machine-readable text layer found — OCR or vision processing required.]"
            )

        records.append({
            "document_id": doc_id,
            "source": rel_source,
            "category": category,
            "content": cleaned_text,
            "file_type": "pdf",
            "page_number": page_number,
            "ocr_required": ocr_required,
            "image_assets": page_images,
        })

    return records


def _format_docx_table(table: Any) -> str:
    """Convert a python-docx Table into a clean, readable pipe-delimited markdown table."""
    rows_text: List[str] = []
    for row in getattr(table, "rows", []):
        cells = [re.sub(r"\s+", " ", (cell.text or "").strip()) for cell in getattr(row, "cells", [])]
        if any(cells):
            rows_text.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows_text)


def _extract_docx_images(
    doc: Any,
    rel_source: str,
    document_id: str,
    assets_dir: Path,
    root_dir: Path,
    max_image_size_bytes: int,
    max_images_per_document: int,
) -> List[Dict[str, Any]]:
    """
    Extract embedded images from a python-docx Document via package relationships.
    Does not assign a fake page_number since DOCX files are reflowable and unpaginated.
    """
    extracted: List[Dict[str, Any]] = []
    seen_hashes: Set[str] = set()
    img_counter = 0

    try:
        rels = getattr(doc.part, "rels", {})
        # Sort by relationship ID (e.g., rId1, rId2, ...) for deterministic order
        for rel_id in sorted(rels.keys()):
            if len(extracted) >= max_images_per_document:
                logger.warning("Reached max_images_per_document limit (%d) for DOCX '%s'", max_images_per_document, rel_source)
                break
            rel = rels[rel_id]
            reltype = getattr(rel, "reltype", "") or ""
            if "image" not in reltype.lower() or getattr(rel, "is_external", False):
                continue
            try:
                target_part = rel.target_part
                blob = getattr(target_part, "blob", None)
                if not blob:
                    continue
                digest = hashlib.sha256(blob).hexdigest()
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)
                img_counter += 1
                meta = _save_extracted_image(
                    image_bytes=blob,
                    rel_source=rel_source,
                    document_id=document_id,
                    image_index=img_counter,
                    assets_dir=assets_dir,
                    root_dir=root_dir,
                    page_number=None,
                    max_image_size_bytes=max_image_size_bytes,
                )
                if meta:
                    extracted.append(meta)
            except Exception as exc:
                logger.warning("Skipping corrupt or unreadable embedded image (%s) in DOCX '%s': %s", rel_id, rel_source, exc)
    except Exception as exc:
        logger.warning("Failed inspecting relationships for embedded images in DOCX '%s': %s", rel_source, exc)

    return extracted


def _load_docx_document(
    path: Path,
    rel_source: str,
    category: str,
    assets_dir: Path,
    root_dir: Path,
    max_image_size_bytes: int,
    max_images_per_document: int,
) -> List[Dict[str, Any]]:
    """
    Extract paragraphs, tables (in document order), and embedded images from a DOCX file.
    """
    try:
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        logger.error("python-docx is not installed; cannot load DOCX '%s': %s", rel_source, exc)
        return []

    try:
        doc = docx.Document(str(path))
    except Exception as exc:
        logger.warning("Skipping corrupt or unreadable DOCX '%s': %s", rel_source, exc)
        return []

    doc_id = _compute_stable_document_id(rel_source, page_number=None)
    blocks: List[str] = []

    try:
        if hasattr(doc, "iter_inner_content"):
            for item in doc.iter_inner_content():
                if isinstance(item, Paragraph):
                    txt = (item.text or "").strip()
                    if txt:
                        blocks.append(txt)
                elif isinstance(item, Table):
                    tbl_txt = _format_docx_table(item)
                    if tbl_txt:
                        blocks.append(tbl_txt)
        else:
            for p in doc.paragraphs:
                txt = (p.text or "").strip()
                if txt:
                    blocks.append(txt)
            for t in doc.tables:
                tbl_txt = _format_docx_table(t)
                if tbl_txt:
                    blocks.append(tbl_txt)
    except Exception as exc:
        logger.warning("Error reading inner content of DOCX '%s': %s", rel_source, exc)

    content = "\n\n".join(blocks).strip()
    if UHID_PATTERN.search(content):
        logger.warning("Skipping DOCX '%s': contains patient UHID record.", rel_source)
        return []

    image_assets = _extract_docx_images(
        doc=doc,
        rel_source=rel_source,
        document_id=doc_id,
        assets_dir=assets_dir,
        root_dir=root_dir,
        max_image_size_bytes=max_image_size_bytes,
        max_images_per_document=max_images_per_document,
    )

    if not content and image_assets:
        content = (
            f"[Image-containing DOCX document {rel_source.replace(chr(92), '/')} "
            f"with {len(image_assets)} extracted image asset(s).]"
        )

    if not content:
        return []

    return [{
        "document_id": doc_id,
        "source": rel_source,
        "category": category,
        "content": content,
        "file_type": "docx",
        "page_number": None,
        "ocr_required": False,
        "image_assets": image_assets,
    }]


def _json_to_readable_text(data: Any, indent_level: int = 0) -> str:
    """
    Safely convert parsed JSON structures (dicts, lists, scalars) into a deterministic,
    human-readable text representation without executing any embedded content.
    """
    prefix = "  " * indent_level
    if isinstance(data, dict):
        lines: List[str] = []
        for k, v in data.items():
            key_str = str(k).strip()
            if isinstance(v, (dict, list)):
                nested = _json_to_readable_text(v, indent_level + 1)
                if nested:
                    lines.append(f"{prefix}{key_str}:\n{nested}")
            else:
                lines.append(f"{prefix}{key_str}: {v}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                nested = _json_to_readable_text(item, indent_level + 1)
                if nested:
                    lines.append(f"{prefix}-\n{nested}")
            else:
                lines.append(f"{prefix}- {item}")
        return "\n".join(lines)
    return f"{prefix}{data}"


def _load_json_document(path: Path, rel_source: str, category: str) -> List[Dict[str, Any]]:
    """Parse, validate, and convert a JSON file into a readable document record."""
    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as exc:
        logger.warning("Failed reading JSON file '%s': %s", rel_source, exc)
        return []

    if not raw_text:
        return []

    try:
        parsed = json.loads(raw_text)
    except Exception as exc:
        logger.warning("Skipping malformed JSON file '%s': %s", rel_source, exc)
        return []

    readable = _json_to_readable_text(parsed).strip()
    if not readable:
        return []

    if UHID_PATTERN.search(readable):
        logger.warning("Skipping JSON '%s': contains patient UHID record.", rel_source)
        return []

    doc_id = _compute_stable_document_id(rel_source, page_number=None)
    return [{
        "document_id": doc_id,
        "source": rel_source,
        "category": category,
        "content": readable,
        "file_type": "json",
        "page_number": None,
        "ocr_required": False,
        "image_assets": [],
    }]


def _load_text_or_markdown_document(
    path: Path,
    rel_source: str,
    category: str,
    file_type: str,
) -> List[Dict[str, Any]]:
    """Load a UTF-8 TXT or Markdown file into a document record."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as exc:
        logger.warning("Failed reading %s file '%s': %s", file_type, rel_source, exc)
        return []

    if not content:
        return []

    if UHID_PATTERN.search(content):
        logger.warning("Skipping %s file '%s': contains patient UHID record.", file_type, rel_source)
        return []

    doc_id = _compute_stable_document_id(rel_source, page_number=None)
    return [{
        "document_id": doc_id,
        "source": rel_source,
        "category": category,
        "content": content,
        "file_type": file_type,
        "page_number": None,
        "ocr_required": False,
        "image_assets": [],
    }]


def load_documents(
    base_dir: Optional[Union[str, Path]] = None,
    assets_dir: Optional[Union[str, Path]] = None,
    max_file_size_bytes: int = DEFAULT_MAX_DOCUMENT_SIZE_BYTES,
    max_image_size_bytes: int = DEFAULT_MAX_IMAGE_SIZE_BYTES,
    max_images_per_document: int = DEFAULT_MAX_IMAGES_PER_DOCUMENT,
) -> List[Dict[str, Any]]:
    """
    Load approved knowledge-base documents from `base_dir` (defaults to `JEEVAN_SETU/knowledge_base`).

    Supports `.pdf`, `.docx`, `.txt`, `.md`, `.markdown`, and `.json`.
    Extracts embedded PDF and DOCX images into `assets_dir` (defaults to `<base_dir>/_extracted_assets`)
    and attaches traceable asset metadata in each returned record's `image_assets` field.
    """
    target_root = Path(base_dir) if base_dir is not None else KNOWLEDGE_BASE_DIR
    if not target_root.exists() or not target_root.is_dir():
        return []

    resolved_root = target_root.resolve()
    resolved_assets_dir = (
        Path(assets_dir).resolve()
        if assets_dir is not None
        else get_knowledge_base_assets_dir(resolved_root)
    )

    documents: List[Dict[str, Any]] = []

    for path in sorted(resolved_root.rglob("*")):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            if not _is_safe_subpath(path, resolved_root):
                logger.warning("Skipping path outside knowledge base root: %s", path.name)
                continue
            if _is_hidden_or_ignored_path(path, resolved_root):
                continue

            ext = path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                logger.debug("Skipping unsupported file extension '%s' (%s)", ext, path.name)
                continue

            try:
                file_size = path.stat().st_size
            except OSError as exc:
                logger.warning("Cannot stat file '%s': %s", path.name, exc)
                continue

            if file_size > max_file_size_bytes:
                logger.warning(
                    "Skipping oversized document '%s' (%d bytes > %d byte limit)",
                    path.name,
                    file_size,
                    max_file_size_bytes,
                )
                continue

            rel_source = str(path.relative_to(resolved_root))
            category = path.parent.name if path.parent != resolved_root else "general"
            file_type = SUPPORTED_EXTENSIONS[ext]

            if file_type == "pdf":
                records = _load_pdf_document(
                    path=path,
                    rel_source=rel_source,
                    category=category,
                    assets_dir=resolved_assets_dir,
                    root_dir=resolved_root,
                    max_image_size_bytes=max_image_size_bytes,
                    max_images_per_document=max_images_per_document,
                )
            elif file_type == "docx":
                records = _load_docx_document(
                    path=path,
                    rel_source=rel_source,
                    category=category,
                    assets_dir=resolved_assets_dir,
                    root_dir=resolved_root,
                    max_image_size_bytes=max_image_size_bytes,
                    max_images_per_document=max_images_per_document,
                )
            elif file_type == "json":
                records = _load_json_document(
                    path=path,
                    rel_source=rel_source,
                    category=category,
                )
            else:
                records = _load_text_or_markdown_document(
                    path=path,
                    rel_source=rel_source,
                    category=category,
                    file_type=file_type,
                )

            documents.extend(records)
        except Exception as exc:
            logger.warning("Unexpected error loading file '%s': %s", path.name, exc)
            continue

    return documents
