"""
tests/test_image_loader.py

Pytest suite for Jeevan Setu Vision Image Loader (`chatbot/vision/image_loader.py`).

Tests:
1. Valid image loading (PNG, JPEG, WebP).
2. Invalid image rejection (text/executable bytes).
3. MIME type & magic-byte validation (extension spoofing rejected).
4. File-size limits enforcement.
5. Corrupted / truncated image handling.
6. Image dimensions, decompression-bomb protection, SHA-256 hash, and metadata.
7. Path-traversal protection (`validate_safe_image_path`).
"""

import io
from pathlib import Path
from PIL import Image, ImageDraw
import pytest

from chatbot.vision.image_loader import (
    detect_magic_mime_and_format,
    encode_image_to_data_url,
    load_and_validate_image_bytes,
    load_image,
    validate_safe_image_path,
)


def _create_synthetic_image_bytes(fmt: str = "PNG", size=(120, 80), mode="RGB") -> bytes:
    img = Image.new(mode, size, color=(240, 248, 255) if mode != "L" else 240)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, size[0] - 10, size[1] - 10], outline=(0, 102, 204) if mode != "L" else 50)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_01_valid_png_jpeg_and_webp_loading(tmp_path: Path):
    for fmt, ext, expected_mime in [
        ("PNG", ".png", "image/png"),
        ("JPEG", ".jpg", "image/jpeg"),
        ("WEBP", ".webp", "image/webp"),
    ]:
        img_bytes = _create_synthetic_image_bytes(fmt=fmt, size=(160, 90))
        img_file = tmp_path / f"synthetic_sample{ext}"
        img_file.write_bytes(img_bytes)

        info = load_image(img_file, base_dir=tmp_path)
        assert info["valid"] is True
        assert info["mime_type"] == expected_mime
        assert info["width"] == 160
        assert info["height"] == 90
        assert info["pixel_count"] == 160 * 90
        assert info["file_size_bytes"] == len(img_bytes)
        assert len(info["content_hash"]) == 64
        data_url = encode_image_to_data_url(info)
        assert data_url.startswith(f"data:{expected_mime};base64,")


def test_02_invalid_and_non_image_content_rejected():
    with pytest.raises(ValueError, match="Unsupported or corrupted image header"):
        load_and_validate_image_bytes(b"This is plain text, not an image file.", filename_hint="fake.png")

    with pytest.raises(ValueError, match="Unsupported image file extension"):
        png_bytes = _create_synthetic_image_bytes("PNG")
        load_and_validate_image_bytes(png_bytes, filename_hint="payload.exe")


def test_03_mime_type_and_extension_spoofing_rejected():
    png_bytes = _create_synthetic_image_bytes("PNG")
    # Spoofed extension: PNG bytes named .jpg
    with pytest.raises(ValueError, match="does not match actual file content format"):
        load_and_validate_image_bytes(png_bytes, filename_hint="spoofed.jpg")


def test_04_file_size_limits_enforced():
    png_bytes = _create_synthetic_image_bytes("PNG", size=(200, 200))
    with pytest.raises(ValueError, match="exceeds maximum limit"):
        load_and_validate_image_bytes(png_bytes, max_file_size_bytes=50)


def test_05_corrupted_image_handling():
    png_bytes = _create_synthetic_image_bytes("PNG", size=(100, 100))
    # Corrupt middle and end of stream
    corrupted = png_bytes[:24] + b"\x00\xff\x00\xff"
    with pytest.raises(ValueError):
        load_and_validate_image_bytes(corrupted, filename_hint="corrupt.png")


def test_06_dimension_and_decompression_bomb_limits():
    png_bytes = _create_synthetic_image_bytes("PNG", size=(300, 200))
    with pytest.raises(ValueError, match="exceed maximum allowed"):
        load_and_validate_image_bytes(png_bytes, max_dimension=100)

    with pytest.raises(ValueError, match=r"decompression[- ]bomb"):
        load_and_validate_image_bytes(png_bytes, max_pixels=10_000)


def test_07_path_traversal_prevented(tmp_path: Path):
    safe_dir = tmp_path / "allowed"
    safe_dir.mkdir()
    outside_file = tmp_path / "outside.png"
    outside_file.write_bytes(_create_synthetic_image_bytes("PNG"))

    with pytest.raises(PermissionError, match="Path traversal"):
        validate_safe_image_path("../outside.png", base_dir=safe_dir)

    with pytest.raises(PermissionError, match="outside the authorized storage directory"):
        validate_safe_image_path(outside_file, base_dir=safe_dir)

