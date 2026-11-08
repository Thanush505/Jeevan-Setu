"""
chatbot/vision/__init__.py

Public exports for the Jeevan Setu Multimodal RAG and Vision Subsystem.
"""

from chatbot.vision.image_loader import (
    ALLOWED_EXTENSIONS,
    DEFAULT_MAX_DIMENSION,
    DEFAULT_MAX_FILE_SIZE_BYTES,
    DEFAULT_MAX_PIXELS,
    DEFAULT_MIN_DIMENSION,
    SUPPORTED_IMAGE_FORMATS,
    detect_magic_mime_and_format,
    encode_image_to_data_url,
    load_and_validate_image_bytes,
    load_image,
    validate_safe_image_path,
)
from chatbot.vision.image_processor import (
    DEFAULT_PATIENT_IMAGE_STORAGE_DIR,
    VALID_PATIENT_ACCESS_LEVELS,
    VALID_PATIENT_IMAGE_TYPES,
    build_multimodal_searchable_text,
    get_authorized_patient_image_file,
    get_authorized_patient_images,
    ingest_knowledge_document_images,
    process_knowledge_image_asset,
    reset_fallback_patient_image_store,
    upload_and_process_patient_image,
)
from chatbot.vision.ocr_service import (
    OCR_DISCLAIMER,
    extract_text_from_image,
    extract_text_from_scanned_page,
    get_ocr_engine,
    get_ocr_engine_info,
)
from chatbot.vision.vision_service import (
    VERIFIED_VISION_MODELS,
    VISION_AI_DISCLAIMER,
    VISION_SYSTEM_PROMPT,
    analyze_image_with_vision,
    is_external_patient_vision_permitted,
    verify_vision_provider_capability,
)

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
    "OCR_DISCLAIMER",
    "extract_text_from_image",
    "extract_text_from_scanned_page",
    "get_ocr_engine",
    "get_ocr_engine_info",
    "VERIFIED_VISION_MODELS",
    "VISION_AI_DISCLAIMER",
    "VISION_SYSTEM_PROMPT",
    "analyze_image_with_vision",
    "is_external_patient_vision_permitted",
    "verify_vision_provider_capability",
    "DEFAULT_PATIENT_IMAGE_STORAGE_DIR",
    "VALID_PATIENT_ACCESS_LEVELS",
    "VALID_PATIENT_IMAGE_TYPES",
    "build_multimodal_searchable_text",
    "get_authorized_patient_image_file",
    "get_authorized_patient_images",
    "ingest_knowledge_document_images",
    "process_knowledge_image_asset",
    "reset_fallback_patient_image_store",
    "upload_and_process_patient_image",
]

