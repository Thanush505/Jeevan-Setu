"""
chatbot/vision/image_loader.py

Safe Image Loading, Content Verification, and Resource-Bounded Normalization
for Jeevan Setu Multimodal RAG.

Responsibilities:
1. Validate actual file content via magic-byte inspection and structural image
   verification (never trusting filename extensions alone).
2. Support JPEG (`image/jpeg`), PNG (`image/png`), and WebP (`image/webp`).
3. Enforce strict file-size, dimension, and total-pixel limits to prevent
   decompression-bomb and resource-exhaustion attacks.
4. Reject corrupted, truncated, zero-byte, or unsupported files safely.
5. Prevent path traversal when loading from disk (`base_dir` boundary check).
6. Normalize loaded images (e.g., RGB conversion, SHA-256 content hashing) for
   downstream OCR and Vision services without ever logging raw image bytes.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple, Union

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger("jeevan_setu.vision.image_loader")

# Decompression-bomb protection
DEFAULT_MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
DEFAULT_MIN_DIMENSION: int = 4
DEFAULT_MAX_DIMENSION: int = 8192
DEFAULT_MAX_PIXELS: int = 25_000_000  # 25 Megapixels

Image.MAX_IMAGE_PIXELS = DEFAULT_MAX_PIXELS

SUPPORTED_IMAGE_FORMATS: Dict[str, str] = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}

CANONICAL_FORMAT_MAP: Dict[str, str] = {
    "PNG": "png",
    "JPEG": "jpeg",
    "JPG": "jpeg",
    "WEBP": "webp",
}

ALLOWED_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp"}


def detect_magic_mime_and_format(data: bytes) -> Tuple[Optional[str], Optional[str]]:
    """
    Inspect raw magic bytes to determine canonical format ('png', 'jpeg', 'webp')
    and MIME type ('image/png', 'image/jpeg', 'image/webp').
    Returns (None, None) if unrecognized or truncated.
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < 12:
        return None, None

    raw = bytes(data)
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        if b"IEND" not in raw[-64:]:
            return None, None
        return "png", "image/png"

    if raw.startswith(b"\xff\xd8\xff"):
        return "jpeg", "image/jpeg"

    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "webp", "image/webp"

    return None, None


def validate_safe_image_path(
    file_path: Union[str, Path],
    base_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Validate a file path against null bytes, directory traversal, and optional
    `base_dir` containment. Raises ValueError or PermissionError if unsafe.
    """
    if not file_path or not isinstance(file_path, (str, Path)):
        raise ValueError("Image file_path must be a non-empty string or Path.")

    raw_str = str(file_path).strip()
    if not raw_str or "\x00" in raw_str:
        raise ValueError("Invalid image path.")

    # Reject explicit parent-directory traversal segments when a relative path is supplied
    parts = Path(raw_str).parts
    if ".." in parts:
        raise PermissionError("Path traversal ('..') is not allowed in image paths.")

    resolved_path = Path(raw_str).resolve()

    if base_dir is not None:
        resolved_base = Path(base_dir).resolve()
        if not resolved_path.is_relative_to(resolved_base):
            raise PermissionError(
                "Access denied: image path resolves outside the authorized storage directory."
            )

    if not resolved_path.exists() or not resolved_path.is_file():
        raise FileNotFoundError(f"Image file not found: {resolved_path.name}")

    return resolved_path


def load_and_validate_image_bytes(
    image_bytes: bytes,
    filename_hint: Optional[str] = None,
    *,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    min_dimension: int = DEFAULT_MIN_DIMENSION,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    normalize_rgb: bool = True,
) -> Dict[str, Any]:
    """
    Validate raw image bytes for magic-byte format, file size, decompression-bomb
    limits, structural integrity, and extension consistency.

    Returns a dictionary containing:
        - `valid`: True
        - `image_format`: 'png' | 'jpeg' | 'webp'
        - `mime_type`: 'image/png' | 'image/jpeg' | 'image/webp'
        - `width`: int
        - `height`: int
        - `pixel_count`: int
        - `color_mode`: str
        - `file_size_bytes`: int
        - `content_hash`: str (SHA-256 hex digest of original bytes)
        - `pil_image`: normalized PIL.Image.Image object
        - `image_bytes`: original validated bytes
    Raises ValueError on any validation failure.
    """
    if not isinstance(image_bytes, (bytes, bytearray)):
        raise ValueError("image_bytes must be bytes.")

    raw = bytes(image_bytes)
    size = len(raw)
    if size == 0:
        raise ValueError("Image data is empty (0 bytes).")

    if size > int(max_file_size_bytes):
        raise ValueError(
            f"Image file size ({size} bytes) exceeds maximum limit ({max_file_size_bytes} bytes)."
        )

    # 1. Check filename extension if provided (reject disguised executables/scripts)
    if filename_hint:
        ext = Path(str(filename_hint)).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported image file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

    # 2. Validate actual magic bytes
    magic_fmt, mime_type = detect_magic_mime_and_format(raw)
    if not magic_fmt or not mime_type:
        raise ValueError(
            "Unsupported or corrupted image header: file content is not a valid PNG, JPEG, or WebP image."
        )

    # If filename extension was provided, ensure it matches the actual magic-byte format
    if filename_hint:
        ext = Path(str(filename_hint)).suffix.lower().lstrip(".")
        if ext:
            norm_ext = "jpeg" if ext in ("jpg", "jpeg") else ext
            if norm_ext != magic_fmt:
                raise ValueError(
                    f"Image extension '.{ext}' does not match actual file content format '{magic_fmt}'."
                )

    # 3. Structural verification & decompression-bomb protection via Pillow
    old_max_pixels = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = int(max_pixels)
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            pil_fmt = CANONICAL_FORMAT_MAP.get(str(probe.format or "").upper())
            if pil_fmt != magic_fmt:
                raise ValueError(
                    f"Image decoder format '{probe.format}' does not match magic header '{magic_fmt}'."
                )
            width, height = probe.size
            if width < min_dimension or height < min_dimension:
                raise ValueError(
                    f"Image dimensions ({width}x{height}) are smaller than minimum ({min_dimension}x{min_dimension})."
                )
            if width > max_dimension or height > max_dimension:
                raise ValueError(
                    f"Image dimensions ({width}x{height}) exceed maximum allowed ({max_dimension}x{max_dimension})."
                )
            pixel_count = width * height
            if pixel_count > max_pixels:
                raise ValueError(
                    f"Image pixel count ({pixel_count}) exceeds decompression-bomb limit ({max_pixels})."
                )
            probe.verify()

        # Re-open after verify() to decode pixel data and normalize
        with Image.open(io.BytesIO(raw)) as decoded:
            decoded.load()
            orig_mode = decoded.mode
            if normalize_rgb and decoded.mode not in ("RGB", "L"):
                if decoded.mode in ("RGBA", "LA") or (
                    decoded.mode == "P" and "transparency" in decoded.info
                ):
                    rgba = decoded.convert("RGBA")
                    bg = Image.new("RGB", rgba.size, (255, 255, 255))
                    bg.paste(rgba, mask=rgba.split()[3])
                    final_img = bg
                else:
                    final_img = decoded.convert("RGB")
            else:
                final_img = decoded.copy()
    except Image.DecompressionBombError as exc:
        raise ValueError("Image rejected: potential decompression bomb detected.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError(f"Corrupted or unreadable image data: {type(exc).__name__}") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = old_max_pixels

    content_hash = hashlib.sha256(raw).hexdigest()

    return {
        "valid": True,
        "image_format": magic_fmt,
        "mime_type": mime_type,
        "width": width,
        "height": height,
        "pixel_count": pixel_count,
        "color_mode": orig_mode,
        "normalized_mode": final_img.mode,
        "file_size_bytes": size,
        "content_hash": content_hash,
        "pil_image": final_img,
        "image_bytes": raw,
    }


def load_image(
    source: Union[str, Path, bytes, io.BytesIO],
    *,
    base_dir: Optional[Union[str, Path]] = None,
    filename_hint: Optional[str] = None,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    min_dimension: int = DEFAULT_MIN_DIMENSION,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    normalize_rgb: bool = True,
) -> Dict[str, Any]:
    """
    Load and validate an image from a file path, raw bytes, or BytesIO stream.
    Enforces path-traversal protection when loading from a file path.
    """
    resolved_path: Optional[Path] = None

    if isinstance(source, (str, Path)):
        resolved_path = validate_safe_image_path(source, base_dir=base_dir)
        file_size = resolved_path.stat().st_size
        if file_size == 0:
            raise ValueError("Image file is empty (0 bytes).")
        if file_size > int(max_file_size_bytes):
            raise ValueError(
                f"Image file size ({file_size} bytes) exceeds maximum limit ({max_file_size_bytes} bytes)."
            )
        raw_bytes = resolved_path.read_bytes()
        hint = filename_hint or resolved_path.name
    elif isinstance(source, io.BytesIO):
        raw_bytes = source.getvalue()
        hint = filename_hint
    elif isinstance(source, (bytes, bytearray)):
        raw_bytes = bytes(source)
        hint = filename_hint
    else:
        raise ValueError(f"Unsupported image source type: {type(source).__name__}.")

    result = load_and_validate_image_bytes(
        raw_bytes,
        filename_hint=hint,
        max_file_size_bytes=max_file_size_bytes,
        min_dimension=min_dimension,
        max_dimension=max_dimension,
        max_pixels=max_pixels,
        normalize_rgb=normalize_rgb,
    )
    result["source_path"] = str(resolved_path) if resolved_path else None
    result["filename"] = resolved_path.name if resolved_path else (hint or f"image.{result['image_format']}")
    return result


def encode_image_to_data_url(
    image_info: Dict[str, Any],
    max_dimension_for_api: int = 2048,
) -> str:
    """
    Convert a validated `image_info` dictionary from `load_image()` into a
    base64 `data:<mime_type>;base64,...` URL suitable for multimodal LLM input.
    Downscales safely if dimensions exceed `max_dimension_for_api`.
    """
    if not isinstance(image_info, dict) or not image_info.get("valid"):
        raise ValueError("encode_image_to_data_url requires a validated image_info dictionary.")

    pil_img: Image.Image = image_info["pil_image"]
    mime_type: str = image_info["mime_type"]
    fmt = "PNG" if mime_type == "image/png" else ("WEBP" if mime_type == "image/webp" else "JPEG")

    w, h = pil_img.size
    if max(w, h) > max_dimension_for_api:
        resized = pil_img.copy()
        resized.thumbnail((max_dimension_for_api, max_dimension_for_api), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format=fmt)
        raw_bytes = buf.getvalue()
    else:
        raw_bytes = image_info["image_bytes"]

    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64_str}"


__all__ = [
    "ALLOWED_EXTENSIONS",
    "DEFAULT_MAX_DIMENSION",
    "DEFAULT_MAX_FILE_SIZE_BYTES",
    "DEFAULT_MAX_PIXELS",
    "DEFAULT_MIN_DIMENSION",
    "SUPPORTED_IMAGE_FORMATS",
    "detect_magic_mime_and_format",
    "encode_image_to_data_url",
    "load_and_validate_image_bytes",
    "load_image",
    "validate_safe_image_path",
]

