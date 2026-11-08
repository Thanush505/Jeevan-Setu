"""
chatbot/vision/ocr_service.py

Local OCR Service for Jeevan Setu Multimodal RAG.

Uses `rapidocr_onnxruntime` (v1.4.4 on ONNX Runtime) as the primary local OCR
engine to extract text from:
- PDF-extracted images
- DOCX-extracted images
- Scanned PDF/document pages
- Authorized standalone clinical image uploads

Clinical & Safety Rules:
1. OCR is strictly a text-extraction utility — NEVER a medical or diagnostic
   interpretation engine.
2. Preserves readable line structure (sorted top-to-bottom, left-to-right by
   bounding box) and exact numeric/unit strings without inventing unreadable values.
3. Reports `mean_confidence` and per-line `confidence` ONLY when the underlying
   OCR engine provides numeric confidence scores.
4. Identifies images/pages where OCR fails (`ocr_status="failed"`) or produces
   insufficient text (`ocr_status="insufficient_text"` / `"empty"`).
5. Sanitizes extracted OCR text via `sanitize_untrusted_text` so text visible
   inside an image cannot execute prompt injection.
6. Never logs raw image bytes, patient details, or full OCR text.
"""

from __future__ import annotations

import importlib.metadata
import io
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from chatbot.rag.context_builder import sanitize_untrusted_text
from chatbot.vision.image_loader import load_image

logger = logging.getLogger("jeevan_setu.vision.ocr_service")

OCR_DISCLAIMER = (
    "Automated OCR character extraction only. Not a medical interpretation or "
    "clinical diagnosis; verify all values against the original image."
)

DEFAULT_MIN_READABLE_CHARS = 3

_CACHED_OCR_ENGINE: Any = None
_CACHED_ENGINE_NAME: str = "rapidocr_onnxruntime"
_CACHED_ENGINE_VERSION: Optional[str] = None


def get_ocr_engine_info() -> Dict[str, Any]:
    """Return installed local OCR engine name, version, and availability status."""
    global _CACHED_ENGINE_VERSION
    try:
        if _CACHED_ENGINE_VERSION is None:
            _CACHED_ENGINE_VERSION = importlib.metadata.version("rapidocr_onnxruntime")
        return {
            "available": True,
            "engine": _CACHED_ENGINE_NAME,
            "version": _CACHED_ENGINE_VERSION,
            "local_execution": True,
        }
    except Exception:
        return {
            "available": False,
            "engine": _CACHED_ENGINE_NAME,
            "version": None,
            "local_execution": True,
        }


def get_ocr_engine() -> Any:
    """Lazy-load and cache the local `RapidOCR` instance."""
    global _CACHED_OCR_ENGINE
    if _CACHED_OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _CACHED_OCR_ENGINE = RapidOCR()
    return _CACHED_OCR_ENGINE


def _sort_and_group_ocr_detections(
    raw_detections: List[Any],
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    """
    Sort OCR detections top-to-bottom and left-to-right, merging boxes on the
    same horizontal line so labels and numeric values remain in reading order.
    """
    if not raw_detections:
        return [], None

    parsed_boxes: List[Dict[str, Any]] = []
    confidences: List[float] = []

    for item in raw_detections:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        bbox = item[0]
        text_val = str(item[1] or "").strip()
        if not text_val:
            continue

        conf_val: Optional[float] = None
        if len(item) >= 3 and item[2] is not None and not isinstance(item[2], bool):
            try:
                conf_val = round(float(item[2]), 4)
                confidences.append(conf_val)
            except (ValueError, TypeError):
                conf_val = None

        # Compute top-Y and left-X from 4-point polygon [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        top_y = 0.0
        left_x = 0.0
        height = 16.0
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            try:
                ys = [ float(pt[1]) for pt in bbox if isinstance(pt, (list, tuple)) and len(pt) >= 2 ]
                xs = [ float(pt[0]) for pt in bbox if isinstance(pt, (list, tuple)) and len(pt) >= 2 ]
                if ys and xs:
                    top_y = min(ys)
                    left_x = min(xs)
                    height = max(4.0, max(ys) - min(ys))
            except (ValueError, TypeError):
                pass

        parsed_boxes.append({
            "text": text_val,
            "confidence": conf_val,
            "bbox": bbox,
            "top_y": top_y,
            "left_x": left_x,
            "height": height,
        })

    if not parsed_boxes:
        return [], None

    # Sort primarily by top_y, then left_x
    parsed_boxes.sort(key=lambda b: (b["top_y"], b["left_x"]))

    # Group boxes that lie on approximately the same horizontal line
    grouped_lines: List[Dict[str, Any]] = []
    current_group: List[Dict[str, Any]] = [parsed_boxes[0]]

    for box in parsed_boxes[1:]:
        prev = current_group[-1]
        line_tol = max(prev["height"], box["height"]) * 0.55
        if abs(box["top_y"] - prev["top_y"]) <= line_tol:
            current_group.append(box)
        else:
            current_group.sort(key=lambda b: b["left_x"])
            line_text = " ".join(b["text"] for b in current_group)
            line_confs = [b["confidence"] for b in current_group if b["confidence"] is not None]
            grouped_lines.append({
                "text": line_text,
                "confidence": round(sum(line_confs) / len(line_confs), 4) if line_confs else None,
                "bbox": current_group[0]["bbox"],
            })
            current_group = [box]

    if current_group:
        current_group.sort(key=lambda b: b["left_x"])
        line_text = " ".join(b["text"] for b in current_group)
        line_confs = [b["confidence"] for b in current_group if b["confidence"] is not None]
        grouped_lines.append({
            "text": line_text,
            "confidence": round(sum(line_confs) / len(line_confs), 4) if line_confs else None,
            "bbox": current_group[0]["bbox"],
        })

    mean_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
    return grouped_lines, mean_conf


def extract_text_from_image(
    image_source: Union[str, Path, bytes, io.BytesIO, Dict[str, Any]],
    *,
    image_id: Optional[str] = None,
    document_id: Optional[str] = None,
    source_path: Optional[str] = None,
    page_number: Optional[int] = None,
    base_dir: Optional[Union[str, Path]] = None,
    min_readable_chars: int = DEFAULT_MIN_READABLE_CHARS,
    ocr_backend: Optional[Callable[[np.ndarray], Tuple[Optional[List[Any]], Any]]] = None,
) -> Dict[str, Any]:
    """
    Run local OCR on a validated image (from path, bytes, or `load_image()` dict)
    and return a structured OCR result preserving source image and page references.
    """
    engine_info = get_ocr_engine_info()

    # 1. Load & validate image if not already a validated dict
    try:
        if isinstance(image_source, dict) and image_source.get("valid") and "pil_image" in image_source:
            img_info = image_source
        else:
            img_info = load_image(image_source, base_dir=base_dir)
    except Exception as exc:
        logger.warning("OCR skipped due to image validation failure: %s", type(exc).__name__)
        return {
            "ocr_status": "failed",
            "ocr_text": "",
            "lines": [],
            "mean_confidence": None,
            "char_count": 0,
            "has_sufficient_text": False,
            "image_id": image_id,
            "document_id": document_id,
            "source_path": source_path,
            "page_number": page_number,
            "engine": engine_info.get("engine"),
            "engine_version": engine_info.get("version"),
            "security_warnings": [],
            "disclaimer": OCR_DISCLAIMER,
            "error": str(exc),
        }

    resolved_source = source_path or img_info.get("source_path") or img_info.get("filename")

    # 2. Execute local OCR engine
    try:
        pil_img = img_info["pil_image"]
        rgb_img = pil_img.convert("RGB") if pil_img.mode != "RGB" else pil_img
        img_array = np.array(rgb_img)

        active_backend = ocr_backend or get_ocr_engine()
        raw_result = active_backend(img_array)
        if isinstance(raw_result, tuple):
            detections = raw_result[0] or []
        elif isinstance(raw_result, list):
            detections = raw_result
        else:
            detections = []
    except Exception as exc:
        logger.error("OCR engine execution failed: %s", type(exc).__name__)
        return {
            "ocr_status": "failed",
            "ocr_text": "",
            "lines": [],
            "mean_confidence": None,
            "char_count": 0,
            "has_sufficient_text": False,
            "image_id": image_id,
            "document_id": document_id,
            "source_path": resolved_source,
            "page_number": page_number,
            "engine": engine_info.get("engine"),
            "engine_version": engine_info.get("version"),
            "security_warnings": [],
            "disclaimer": OCR_DISCLAIMER,
            "error": f"OCR engine failure: {exc}",
        }

    lines, mean_conf = _sort_and_group_ocr_detections(detections)
    raw_joined = "\n".join(line["text"] for line in lines).strip()
    sanitized_text, warnings = sanitize_untrusted_text(raw_joined)

    #Sanitize individual lines as well
    sanitized_lines: List[Dict[str, Any]] = []
    for line in lines:
        clean_line, _ = sanitize_untrusted_text(line["text"])
        if clean_line:
            sanitized_lines.append({
                "text": clean_line,
                "confidence": line.get("confidence"),
                "bbox": line.get("bbox"),
            })

    alnum_chars = sum(1 for ch in sanitized_text if ch.isalnum())
    has_sufficient = alnum_chars >= max(1, int(min_readable_chars))

    if not sanitized_text:
        status = "empty"
    elif not has_sufficient:
        status = "insufficient_text"
    else:
        status = "completed"

    return {
        "ocr_status": status,
        "ocr_text": sanitized_text,
        "lines": sanitized_lines,
        "mean_confidence": mean_conf,
        "char_count": len(sanitized_text),
        "has_sufficient_text": has_sufficient,
        "image_id": image_id,
        "document_id": document_id,
        "source_path": resolved_source,
        "page_number": page_number,
        "content_hash": img_info.get("content_hash"),
        "engine": engine_info.get("engine"),
        "engine_version": engine_info.get("version"),
        "security_warnings": warnings,
        "disclaimer": OCR_DISCLAIMER,
        "error": None,
    }


def extract_text_from_scanned_page(
    page_images: List[Dict[str, Any]],
    *,
    document_id: str,
    source_path: str,
    page_number: Optional[int] = None,
    base_dir: Optional[Union[str, Path]] = None,
    ocr_backend: Optional[Callable[[np.ndarray], Tuple[Optional[List[Any]], Any]]] = None,
) -> Dict[str, Any]:
    """
    Aggregate OCR results across one or more images extracted from a scanned
    PDF/document page while preserving page and asset provenance.
    """
    if not page_images:
        return {
            "ocr_status": "empty",
            "ocr_text": "",
            "image_results": [],
            "mean_confidence": None,
            "has_sufficient_text": False,
            "document_id": document_id,
            "source_path": source_path,
            "page_number": page_number,
            "disclaimer": OCR_DISCLAIMER,
            "error": "No page images available for OCR.",
        }

    texts: List[str] = []
    confs: List[float] = []
    image_results: List[Dict[str, Any]] = []
    any_failed = False

    for asset in page_images:
        if not isinstance(asset, dict):
            continue
        asset_rel = asset.get("asset_path")
        img_id = asset.get("image_id")
        if not asset_rel:
            continue

        target_path = (Path(base_dir) / asset_rel) if base_dir else Path(asset_rel)
        res = extract_text_from_image(
            target_path,
            image_id=img_id,
            document_id=document_id,
            source_path=source_path,
            page_number=page_number if page_number is not None else asset.get("page_number"),
            base_dir=base_dir,
            ocr_backend=ocr_backend,
        )
        image_results.append(res)
        if res["ocr_status"] == "failed":
            any_failed = True
        if res.get("ocr_text"):
            texts.append(res["ocr_text"])
        if res.get("mean_confidence") is not None:
            confs.append(float(res["mean_confidence"]))

    combined_text = "\n\n".join(texts).strip()
    has_sufficient = sum(1 for c in combined_text if c.isalnum()) >= DEFAULT_MIN_READABLE_CHARS
    mean_conf = round(sum(confs) / len(confs), 4) if confs else None

    if combined_text and has_sufficient:
        status = "completed"
    elif any_failed and not combined_text:
        status = "failed"
    elif combined_text:
        status = "insufficient_text"
    else:
        status = "empty"

    return {
        "ocr_status": status,
        "ocr_text": combined_text,
        "image_results": image_results,
        "mean_confidence": mean_conf,
        "has_sufficient_text": has_sufficient,
        "document_id": document_id,
        "source_path": source_path,
        "page_number": page_number,
        "disclaimer": OCR_DISCLAIMER,
        "error": None,
    }


__all__ = [
    "DEFAULT_MIN_READABLE_CHARS",
    "OCR_DISCLAIMER",
    "extract_text_from_image",
    "extract_text_from_scanned_page",
    "get_ocr_engine",
    "get_ocr_engine_info",
]

