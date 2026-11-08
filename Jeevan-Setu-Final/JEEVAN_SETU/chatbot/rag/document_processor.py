"""
chatbot/rag/document_processor.py — Document Cleaning, Token-Aware Chunking & Multimodal Metadata Preservation
for Jeevan Setu RAG.

Responsibilities:
1. Text Cleaning (`clean_text`, `clean_document_content`):
   - Normalizes line endings (`\\r\\n`, `\\r` -> `\\n`), non-breaking spaces, zero-width characters,
     and safe extraction artifacts while strictly preserving paragraph boundaries, Markdown/clinical
     headings, numbered lists, bullet points, pipe-delimited tables, and exact clinical values/units.
2. Intelligent Token-Aware Chunking (`chunk_text`, `estimate_token_count`):
   - Configurable chunk size (default: 800 tokens) and overlap (default: 120 tokens) using a
     documented, deterministic clinical subword token approximation.
   - Respects paragraph, heading, list, table, and sentence boundaries; splits oversized paragraphs
     safely at sentence/word boundaries; never drops text between chunks; keeps clinical labels attached
     to their values.
3. Metadata & Multimodal Readiness (`process_document`, `process_documents`):
   - Preserves `chunk_id`, `document_id`, `source`, `category`, `file_type`, `page_number`,
     `chunk_index`, `total_chunks`, `content`, `content_hash`, and `image_assets`.
   - Generates deterministic, collision-resistant `chunk_id`s from stable document identity, version,
     chunk position, and content hash.
   - Keeps image asset references separate from raw image bytes/base64, never calls OCR or OpenRouter,
     and blocks identifiable patient records (e.g., `UHID-YYYY-NNNNN` or `patient_id`) from shared
     knowledge ingestion.
"""

import copy
import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("jeevan_setu.rag.document_processor")

DEFAULT_CHUNK_SIZE_TOKENS = 800
DEFAULT_CHUNK_OVERLAP_TOKENS = 120
DEFAULT_DOCUMENT_VERSION = "1.0"

# Guardrail against ingesting identifiable patient records or patient-specific images into shared RAG
UHID_PATTERN = re.compile(r"\bUHID-\d{4}-\d{5}\b", re.IGNORECASE)
PROHIBITED_PATIENT_FIELDS = frozenset({
    "patient_id",
    "patient_image_id",
    "patient_name",
    "uhid",
})
BASE64_IMAGE_URI_PATTERN = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+", re.IGNORECASE)

# Safe extraction artifact patterns
ZERO_WIDTH_OR_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b\u200c\u200d\ufeff\ufffe]")
NON_BREAKING_SPACE_RE = re.compile(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")

# Deterministic clinical token approximation:
# Matches words, numbers/decimals, units/ranges, or individual punctuation symbols.
TOKEN_UNIT_RE = re.compile(r"[A-Za-z0-9]+(?:[./_-][A-Za-z0-9]+)*|[^\sA-Za-z0-9]", re.UNICODE)

# Structural line detectors
HEADING_LINE_RE = re.compile(
    r"^(?:#{1,6}\s+\S.*|(?:SECTION|CHAPTER|PROTOCOL|GUIDELINE|SOP|APPENDIX|PART)\s+[A-Z0-9IVX]+[:.\s-].*|[A-Z][A-Z0-9\s/()&-]{3,80}:?)$"
)
LIST_ITEM_LINE_RE = re.compile(
    r"^\s*(?:[-*•‣▪▸◦]\s+|\(?[0-9]{1,3}[.)]\s+|\(?[a-zA-Z][.)]\s+|\([ivxlcdmIVXLCDM]+\)\s+)\S"
)
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")

# Abbreviations that should not trigger a false sentence split after '.'
ABBREVIATION_SUFFIX_RE = re.compile(
    r"\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|St|Fig|Tab|Eq|Ref|No|Vol|Ch|Sec|vs|etc|e\.g|i\.e|approx|min|max|hr|hrs|mg|mcg|kg|ml|mL|dL|mmol|mEq|mmHg|SpO2|FiO2|PaO2|PaCO2|bpm)\.$",
    re.IGNORECASE,
)


def estimate_token_count(text: str) -> int:
    """
    Deterministic token count approximation for clinical and technical English text.

    Documentation of approximation:
    - Counts lexical words, numerical/unit tokens, and punctuation symbols via `TOKEN_UNIT_RE`,
      and accounts for subword splitting on long medical terms (> 8 characters) by adding
      1 subword token per additional 6 characters.
    - Also enforces a character floor (`ceil(len(text) / 4)`) so dense symbol/numeric sequences
      never underestimate token budget.
    - Purely deterministic and offline (does not claim exact model-specific BPE counts).
    """
    if not isinstance(text, str) or not text.strip():
        return 0
    raw_tokens = TOKEN_UNIT_RE.findall(text)
    if not raw_tokens:
        return 0
    subword_adjusted = 0
    for tok in raw_tokens:
        t_len = len(tok)
        if t_len > 8 and tok[0].isalnum():
            subword_adjusted += 1 + (t_len - 3) // 6
        else:
            subword_adjusted += 1
    char_based_floor = (len(text.strip()) + 3) // 4
    return max(subword_adjusted, char_based_floor)


def _clean_single_line(line: str) -> str:
    """
    Clean a single line while preserving list indentation, table pipes, headings,
    and clinical symbols/units (`mg/dL`, `mmHg`, `SpO2 >= 94%`, `38.5 °C`, `±`, `≤`, `≥`).
    """
    if not line:
        return ""

    # Replace non-breaking spaces with standard spaces and expand tabs
    cleaned = NON_BREAKING_SPACE_RE.sub(" ", line).replace("\t", "    ")
    # Strip invisible zero-width and non-printable control characters
    cleaned = ZERO_WIDTH_OR_CONTROL_RE.sub("", cleaned)

    stripped = cleaned.strip()
    if not stripped:
        return ""

    # Preserve pipe-delimited table rows cleanly
    if TABLE_LINE_RE.match(stripped):
        cells = [re.sub(r" {2,}", " ", c.strip()) for c in stripped.strip("|").split("|")]
        return "| " + " | ".join(cells) + " |"

    # Preserve leading indentation for nested lists (up to 8 spaces, normalized to multiples of 2)
    leading_spaces = len(cleaned) - len(cleaned.lstrip(" "))
    indent = ""
    if leading_spaces > 0 and LIST_ITEM_LINE_RE.match(cleaned):
        indent = " " * min(8, (leading_spaces // 2) * 2 or 2)

    # Collapse internal runs of multiple horizontal spaces into a single space
    body = re.sub(r" {2,}", " ", stripped)
    return f"{indent}{body}"


def clean_text(text: str) -> str:
    """
    Normalize whitespace, line endings, and safe extraction artifacts while preserving:
    - Paragraph boundaries (double newlines `\\n\\n`)
    - Headings and section titles
    - Numbered and bulleted lists
    - Pipe-delimited table structures
    - Clinical terminology, numerical values, units, comparators, and punctuation

    Never rewrites, summarizes, or medically interprets source text.
    """
    if not isinstance(text, str):
        raise ValueError(f"Expected 'text' to be a str, got {type(text).__name__}.")
    if not text:
        return ""

    # 1. Normalize all line endings (\r\n and \r -> \n) and form feeds (\f -> paragraph break)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")

    # 2. Repair hyphenated line-break artifacts ONLY when a lowercase word was broken across lines
    #    (e.g. "cardio-\nvascular" -> "cardiovascular"), never touching clinical ranges ("ICU-HDU", "10-20")
    normalized = re.sub(r"([a-z]{3,})-\n\s*([a-z]{3,})\b", r"\1\2", normalized)

    # 3. Clean line by line and collapse 3+ consecutive blank lines into a single blank line (\n\n)
    raw_lines = normalized.split("\n")
    output_lines: List[str] = []
    blank_streak = 0

    for raw_line in raw_lines:
        cleaned_line = _clean_single_line(raw_line)
        if not cleaned_line:
            blank_streak += 1
            if blank_streak == 1 and output_lines:
                output_lines.append("")
        else:
            blank_streak = 0
            output_lines.append(cleaned_line)

    while output_lines and output_lines[-1] == "":
        output_lines.pop()

    return "\n".join(output_lines)


def clean_document_content(document: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    """
    Clean either a raw string or a document dictionary (returning a new dictionary copy
    without mutating the input record).
    """
    if isinstance(document, str):
        return clean_text(document)
    if not isinstance(document, dict):
        raise ValueError(f"Expected str or dict for clean_document_content, got {type(document).__name__}.")
    doc_copy = copy.deepcopy(document)
    raw_content = doc_copy.get("content")
    if isinstance(raw_content, str):
        doc_copy["content"] = clean_text(raw_content)
    elif raw_content is None:
        doc_copy["content"] = ""
    else:
        doc_copy["content"] = clean_text(str(raw_content))
    return doc_copy


def _is_heading_block(block: str) -> bool:
    """Return True if a single-line block is a section heading that should stay attached to following text."""
    lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
    if len(lines) != 1:
        return False
    line = lines[0]
    if len(line) > 120:
        return False
    if line.startswith("#"):
        return True
    if HEADING_LINE_RE.match(line) and not line.endswith("."):
        return True
    return False


def _split_into_paragraphs_preserving_headings(cleaned_text: str) -> List[str]:
    """
    Split cleaned text on paragraph boundaries (`\\n\\n`) and bind standalone headings
    to the immediately following paragraph so headings are not stranded alone at the end of a chunk.
    """
    raw_blocks = [b.strip() for b in cleaned_text.split("\n\n") if b.strip()]
    if not raw_blocks:
        return []

    merged_blocks: List[str] = []
    idx = 0
    while idx < len(raw_blocks):
        current = raw_blocks[idx]
        if _is_heading_block(current) and (idx + 1) < len(raw_blocks):
            merged_blocks.append(f"{current}\n\n{raw_blocks[idx + 1]}")
            idx += 2
        else:
            merged_blocks.append(current)
            idx += 1
    return merged_blocks


def _split_text_into_sentences(text: str) -> List[str]:
    """
    Split a paragraph or block into sentence/line units without breaking:
    - Decimal numbers (`38.6`, `7.35`, `0.9%`)
    - Common clinical abbreviations (`Dr.`, `mg.`, `approx.`, `e.g.`)
    - Clinical label: value pairs (`Heart Rate: 112 bpm`, `SpO2: 94%`)
    - List items or table rows on separate lines
    """
    if "\n" in text:
        lines = [ln for ln in text.split("\n") if ln.strip()]
        units: List[str] = []
        for ln in lines:
            if LIST_ITEM_LINE_RE.match(ln) or TABLE_LINE_RE.match(ln) or _is_heading_block(ln):
                units.append(ln)
            else:
                sub_sents = _split_single_line_sentences(ln)
                units.extend(sub_sents)
        return units
    return _split_single_line_sentences(text)


def _split_single_line_sentences(line: str) -> List[str]:
    """Split a single line into sentences on terminal punctuation followed by whitespace."""
    line_str = line.strip()
    if not line_str:
        return []

    candidate_parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[\"#])", line_str)
    if len(candidate_parts) <= 1:
        return [line_str]

    sentences: List[str] = []
    buffer = candidate_parts[0]
    for part in candidate_parts[1:]:
        # Avoid splitting if buffer ends with a known abbreviation or a standalone number list marker ("1.")
        if ABBREVIATION_SUFFIX_RE.search(buffer) or re.search(r"(?:^|\s)\d{1,3}\.$", buffer):
            buffer = f"{buffer} {part}"
        else:
            sentences.append(buffer.strip())
            buffer = part
    if buffer.strip():
        sentences.append(buffer.strip())
    return sentences


def _split_oversized_unit_by_words(
    unit_text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> List[str]:
    """
    Safely split an oversized single sentence/line into word-bounded segments that respect `max_tokens`,
    while keeping `Label: Value Unit` triples intact whenever possible.
    """
    words = unit_text.split(" ")
    if not words:
        return []

    # Bind "Label:" to its immediate value token so clinical labels aren't separated from values
    bound_tokens: List[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if w.endswith(":") and (i + 1) < len(words) and len(w) <= 30:
            bound_piece = f"{w} {words[i + 1]}"
            if (i + 2) < len(words) and re.match(r"^(?:mmHg|bpm|mg/dL|mcg/kg/min|mL/hr|L/min|%|°C|mmol/L|mEq/L)$", words[i + 2]):
                bound_piece = f"{bound_piece} {words[i + 2]}"
                i += 3
            else:
                i += 2
            bound_tokens.append(bound_piece)
        else:
            bound_tokens.append(w)
            i += 1

    segments: List[str] = []
    current_words: List[str] = []
    current_tokens = 0

    for piece in bound_tokens:
        piece_tokens = max(1, estimate_token_count(piece))
        if current_words and (current_tokens + piece_tokens) > max_tokens:
            segments.append(" ".join(current_words).strip())
            # Build word overlap for continuity
            if overlap_tokens > 0:
                overlap_buf: List[str] = []
                overlap_cnt = 0
                for prev_w in reversed(current_words):
                    pw_tok = max(1, estimate_token_count(prev_w))
                    if overlap_cnt + pw_tok > overlap_tokens and overlap_buf:
                        break
                    overlap_buf.insert(0, prev_w)
                    overlap_cnt += pw_tok
                # Ensure we always advance by at least one word
                if len(overlap_buf) >= len(current_words):
                    overlap_buf = current_words[-1:] if len(current_words) > 1 else []
                current_words = list(overlap_buf)
                current_tokens = estimate_token_count(" ".join(current_words)) if current_words else 0
            else:
                current_words = []
                current_tokens = 0

        current_words.append(piece)
        current_tokens = estimate_token_count(" ".join(current_words))

    if current_words:
        final_seg = " ".join(current_words).strip()
        if final_seg and (not segments or final_seg != segments[-1]):
            segments.append(final_seg)

    return segments


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> List[str]:
    """
    Split text into overlapping token-targeted chunks while preserving paragraph, heading,
    table, list, and sentence boundaries.

    Args:
        text: Input document text to clean and chunk.
        chunk_size: Target maximum tokens per chunk (default: 800 tokens).
        overlap: Target overlap tokens between consecutive chunks (default: 120 tokens).

    Returns:
        List of non-empty cleaned chunk strings in original document order.
    """
    if not isinstance(text, str):
        raise ValueError(f"Expected 'text' to be a str, got {type(text).__name__}.")
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")
    if not isinstance(overlap, int) or isinstance(overlap, bool) or overlap < 0:
        raise ValueError("overlap must be a non-negative integer.")
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be strictly less than chunk_size ({chunk_size}).")

    cleaned = clean_text(text)
    if not cleaned:
        return []

    # Fast path for short documents that fit in a single chunk
    total_tokens = estimate_token_count(cleaned)
    if total_tokens <= chunk_size:
        return [cleaned]

    paragraphs = _split_into_paragraphs_preserving_headings(cleaned)
    if not paragraphs:
        return [cleaned]

    # Decompose any paragraph that exceeds chunk_size into sentence/line or word units
    # Each item is a tuple: (unit_text, separator_before_unit)
    atomic_units: List[Tuple[str, str]] = []
    for p_idx, para in enumerate(paragraphs):
        para_sep = "\n\n" if p_idx > 0 else ""
        if estimate_token_count(para) <= chunk_size:
            atomic_units.append((para, para_sep))
        else:
            sentences = _split_text_into_sentences(para)
            for s_idx, sent in enumerate(sentences):
                sent_sep = para_sep if s_idx == 0 else ("\n" if "\n" in para else " ")
                if estimate_token_count(sent) <= chunk_size:
                    atomic_units.append((sent, sent_sep))
                else:
                    word_segs = _split_oversized_unit_by_words(sent, chunk_size, overlap)
                    for w_idx, w_seg in enumerate(word_segs):
                        w_sep = sent_sep if w_idx == 0 else " "
                        atomic_units.append((w_seg, w_sep))

    chunks: List[str] = []
    current_units: List[Tuple[str, str]] = []

    def _join_units(units_list: Sequence[Tuple[str, str]]) -> str:
        if not units_list:
            return ""
        parts = [units_list[0][0]]
        for u_text, u_sep in units_list[1:]:
            sep = u_sep if u_sep else " "
            parts.append(sep + u_text)
        return "".join(parts).strip()

    idx = 0
    num_units = len(atomic_units)
    while idx < num_units:
        unit_text, unit_sep = atomic_units[idx]
        candidate_units = current_units + [(unit_text, unit_sep)]
        candidate_str = _join_units(candidate_units)
        candidate_tokens = estimate_token_count(candidate_str)

        if not current_units or candidate_tokens <= chunk_size:
            current_units.append((unit_text, unit_sep))
            idx += 1
        else:
            # Emit current chunk
            chunk_str = _join_units(current_units)
            if chunk_str and (not chunks or chunk_str != chunks[-1]):
                chunks.append(chunk_str)

            # Build overlap tail from `current_units`
            if overlap > 0 and len(current_units) > 1:
                overlap_units: List[Tuple[str, str]] = []
                for prev_unit in reversed(current_units):
                    trial = [prev_unit] + overlap_units
                    trial_tokens = estimate_token_count(_join_units(trial))
                    if trial_tokens > overlap and overlap_units:
                        break
                    overlap_units.insert(0, prev_unit)

                # Never retain all units in `current_units` (must make forward progress)
                if len(overlap_units) >= len(current_units):
                    overlap_units = current_units[-1:]
                # Also ensure overlap_units + next unit won't immediately overflow chunk_size
                while overlap_units and estimate_token_count(
                    _join_units(overlap_units + [(unit_text, unit_sep)])
                ) > chunk_size:
                    overlap_units.pop(0)
                current_units = overlap_units
            else:
                current_units = []

    if current_units:
        final_chunk = _join_units(current_units)
        if final_chunk and (not chunks or final_chunk != chunks[-1]):
            chunks.append(final_chunk)

    return [c for c in chunks if c]


def _compute_content_hash(content: str) -> str:
    """Compute SHA-256 hex digest of cleaned chunk content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _compute_deterministic_chunk_id(
    document_id: str,
    version: str,
    chunk_index: int,
    content_hash: str,
    page_number: Optional[int] = None,
) -> str:
    """
    Generate a deterministic, collision-resistant chunk ID from stable document identity,
    version, optional page number, chunk index, and content hash.
    """
    safe_doc_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(document_id).strip()).strip("_") or "doc"
    safe_ver = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(version or DEFAULT_DOCUMENT_VERSION).strip()).strip("_") or "1_0"
    identity_seed = f"{safe_doc_id}|v={safe_ver}|p={page_number}|c={chunk_index}|h={content_hash[:16]}"
    short_hash = hashlib.sha256(identity_seed.encode("utf-8")).hexdigest()[:10]
    return f"{safe_doc_id}_v{safe_ver}_c{chunk_index}_{short_hash}"


def _derive_fallback_document_id(source: str, page_number: Optional[int] = None) -> str:
    """Derive a deterministic `document_id` if a caller passes a minimal dict without `document_id`."""
    normalized_source = str(source or "unknown").replace("\\", "/").strip() or "unknown"
    key = f"{normalized_source}#p{page_number}" if page_number is not None else normalized_source
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(normalized_source).stem).strip("_").lower() or "doc"
    if page_number is not None:
        return f"doc_{stem}_p{page_number}_{digest}"
    return f"doc_{stem}_{digest}"


def _infer_file_type(document: Dict[str, Any], source: str) -> str:
    """Infer normalized file_type from document record or source file extension."""
    raw_ft = document.get("file_type")
    if isinstance(raw_ft, str) and raw_ft.strip():
        ft_lower = raw_ft.strip().lower().lstrip(".")
        if ft_lower == "md":
            return "markdown"
        return ft_lower

    ext = Path(str(source or "")).suffix.lower()
    ext_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".txt": "txt",
        ".md": "markdown",
        ".markdown": "markdown",
        ".json": "json",
    }
    return ext_map.get(ext, "txt")


def _sanitize_image_assets(
    raw_assets: Any,
    document_id: str,
    source: str,
    file_type: str,
    page_number: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Validate and deep-copy extracted image asset metadata references from `document_loader.py`
    for multimodal readiness:
    - Associates each image with `document_id` and `source_document`.
    - Preserves `page_number` for PDFs and ensures `None` for unpaginated DOCX files.
    - Strips any accidental raw image bytes (`bytes`/`bytearray`) or base64 data URIs.
    - Rejects patient-specific image records from entering the shared knowledge workflow.
    """
    if not raw_assets or not isinstance(raw_assets, (list, tuple)):
        return []

    sanitized: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    norm_source = str(source or "unknown").replace("\\", "/")

    for idx, asset in enumerate(raw_assets):
        if not isinstance(asset, dict):
            continue

        # Reject patient-specific images from shared knowledge ingestion
        if any(k in asset for k in PROHIBITED_PATIENT_FIELDS):
            logger.warning("Skipping patient-specific image asset in shared RAG processor.")
            continue

        asset_path = asset.get("asset_path")
        if not isinstance(asset_path, str) or not asset_path.strip():
            continue
        asset_path_clean = asset_path.strip().replace("\\", "/")
        if BASE64_IMAGE_URI_PATTERN.search(asset_path_clean):
            logger.warning("Skipping base64-encoded image URI in asset_path; only file references are allowed.")
            continue

        image_id = str(asset.get("image_id") or f"img_{document_id}_{idx + 1}").strip()
        if image_id in seen_ids:
            continue
        seen_ids.add(image_id)

        # Preserve PDF page association; never invent page numbers for DOCX
        if file_type == "docx":
            img_page = None
        else:
            raw_img_page = asset.get("page_number", page_number)
            img_page = int(raw_img_page) if isinstance(raw_img_page, int) and not isinstance(raw_img_page, bool) and raw_img_page >= 1 else page_number

        clean_item: Dict[str, Any] = {
            "image_id": image_id,
            "document_id": str(asset.get("document_id") or document_id),
            "source_document": str(asset.get("source_document") or norm_source).replace("\\", "/"),
            "page_number": img_page,
            "image_format": str(asset.get("image_format") or "png").lower(),
            "file_size": int(asset.get("file_size") or 0) if isinstance(asset.get("file_size"), (int, float)) else 0,
            "asset_path": asset_path_clean,
        }
        sanitized.append(clean_item)

    return sanitized


def process_document(
    document: Dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Process a single loaded document record (from `document_loader.py`) into one or more
    cleaned, metadata-enriched chunk dictionaries compatible with `embedding_service.py`
    and `vector_store.py`.

    Does not mutate the input `document` dictionary.
    Returns an empty list if `document` is invalid, empty, or contains identifiable patient records.
    """
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")
    if not isinstance(overlap, int) or isinstance(overlap, bool) or overlap < 0:
        raise ValueError("overlap must be a non-negative integer.")
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be strictly less than chunk_size ({chunk_size}).")

    if not isinstance(document, dict):
        logger.warning("Skipping invalid document record of type %s (expected dict).", type(document).__name__)
        return []

    # Guardrail: reject identifiable patient records or patient-specific medical images
    if any(k in document and document[k] is not None for k in PROHIBITED_PATIENT_FIELDS):
        logger.warning("Skipping document record containing prohibited patient-specific fields.")
        return []

    raw_content = document.get("content")
    if not isinstance(raw_content, str) or not raw_content.strip():
        return []

    if BASE64_IMAGE_URI_PATTERN.search(raw_content):
        raw_content = BASE64_IMAGE_URI_PATTERN.sub("[embedded_image_reference]", raw_content)

    if UHID_PATTERN.search(raw_content):
        logger.warning("Skipping document record containing identifiable patient UHID.")
        return []

    raw_source = document.get("source")
    source = str(raw_source).strip() if isinstance(raw_source, str) and raw_source.strip() else "unknown"
    if UHID_PATTERN.search(source):
        logger.warning("Skipping document record with patient UHID in source path.")
        return []

    raw_category = document.get("category")
    category = str(raw_category).strip() if isinstance(raw_category, str) and raw_category.strip() else "general"

    file_type = _infer_file_type(document, source)

    # Page number rules: preserve positive integer page_number for PDFs; never invent page numbers for DOCX
    raw_page = document.get("page_number")
    page_number: Optional[int] = None
    if file_type != "docx" and isinstance(raw_page, int) and not isinstance(raw_page, bool) and raw_page >= 1:
        page_number = raw_page

    raw_doc_id = document.get("document_id")
    if isinstance(raw_doc_id, str) and raw_doc_id.strip():
        document_id = raw_doc_id.strip()
    else:
        document_id = _derive_fallback_document_id(source, page_number=page_number)

    raw_version = document.get("document_version") or document.get("version") or DEFAULT_DOCUMENT_VERSION
    document_version = str(raw_version).strip() if isinstance(raw_version, (str, int, float)) and str(raw_version).strip() else DEFAULT_DOCUMENT_VERSION

    ocr_required = bool(document.get("ocr_required", False))

    image_assets = _sanitize_image_assets(
        raw_assets=document.get("image_assets"),
        document_id=document_id,
        source=source,
        file_type=file_type,
        page_number=page_number,
    )

    text_chunks = chunk_text(raw_content, chunk_size=chunk_size, overlap=overlap)
    if not text_chunks:
        return []

    # Deduplicate identical chunks within the same document record while preserving order
    unique_text_chunks: List[str] = []
    seen_chunk_hashes: Set[str] = set()
    for ch in text_chunks:
        c_hash = _compute_content_hash(ch)
        if c_hash not in seen_chunk_hashes:
            seen_chunk_hashes.add(c_hash)
            unique_text_chunks.append(ch)

    total_chunks = len(unique_text_chunks)
    processed_chunks: List[Dict[str, Any]] = []

    for idx, chunk_str in enumerate(unique_text_chunks):
        content_hash = _compute_content_hash(chunk_str)
        chunk_id = _compute_deterministic_chunk_id(
            document_id=document_id,
            version=document_version,
            chunk_index=idx,
            content_hash=content_hash,
            page_number=page_number,
        )

        # Build ChromaDB-safe scalar metadata dictionary (all values str, int, float, or bool)
        chroma_metadata: Dict[str, Union[str, int, float, bool]] = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "source": source,
            "category": category,
            "file_type": file_type,
            "chunk_index": idx,
            "total_chunks": total_chunks,
            "content_hash": content_hash,
            "ocr_required": ocr_required,
            "has_images": len(image_assets) > 0,
            "image_count": len(image_assets),
        }
        if page_number is not None:
            chroma_metadata["page_number"] = page_number
        if image_assets:
            chroma_metadata["image_ids"] = ",".join(a["image_id"] for a in image_assets)

        chunk_record: Dict[str, Any] = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "source": source,
            "category": category,
            "file_type": file_type,
            "page_number": page_number,
            "chunk_index": idx,
            "total_chunks": total_chunks,
            "content": chunk_str,
            "content_hash": content_hash,
            "ocr_required": ocr_required,
            "image_assets": copy.deepcopy(image_assets),
            "metadata": chroma_metadata,
        }
        processed_chunks.append(chunk_record)

    return processed_chunks


def process_documents(
    documents: Sequence[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Process a collection of loaded document records into deduplicated, metadata-enriched
    chunk dictionaries ready for embedding generation and ChromaDB storage.

    Args:
        documents: Sequence of document dicts produced by `document_loader.load_documents()`.
        chunk_size: Target maximum tokens per chunk (default: 800).
        overlap: Target overlap tokens between consecutive chunks (default: 120).

    Returns:
        List of processed chunk dictionaries.
    """
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")
    if not isinstance(overlap, int) or isinstance(overlap, bool) or overlap < 0:
        raise ValueError("overlap must be a non-negative integer.")
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be strictly less than chunk_size ({chunk_size}).")

    if not documents:
        return []
    if not isinstance(documents, (list, tuple)):
        logger.warning("Expected list or tuple of documents, got %s.", type(documents).__name__)
        return []

    all_chunks: List[Dict[str, Any]] = []
    seen_chunk_keys: Set[Tuple[str, str]] = set()

    for doc in documents:
        doc_chunks = process_document(doc, chunk_size=chunk_size, overlap=overlap)
        for chunk in doc_chunks:
            dedup_key = (chunk["chunk_id"], chunk["content_hash"])
            if dedup_key in seen_chunk_keys:
                continue
            seen_chunk_keys.add(dedup_key)
            all_chunks.append(chunk)

    return all_chunks
