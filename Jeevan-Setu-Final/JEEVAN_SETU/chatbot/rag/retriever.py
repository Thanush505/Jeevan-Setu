"""
chatbot/rag/retriever.py — Semantic Knowledge Base Retriever for Jeevan Setu RAG.

Responsibilities:
1. Query Embedding (`embed_query`):
   - Generates 384-dimensional query embeddings exclusively via `get_embedding(query)`
     from `chatbot/rag/embedding_service.py` (`sentence-transformers/all-MiniLM-L6-v2`).
   - Validates non-empty string input and verifies 384 finite float values.
2. Semantic Retrieval & Filtering (`retrieve_relevant_chunks`, `retrieve_with_filters`,
   `retrieve_by_document_id`, `retrieve_multiple_queries`):
   - Searches the approved shared ChromaDB collection (`jeevan_setu_knowledge`) via `VectorStore`.
   - Supports optional validated filters: `category`, `document_id`, `file_type`, and `document_version`.
   - Normalizes ChromaDB cosine distance into a bounded relevance score (`relevance_score = 1.0 - distance / 2.0`
     for cosine distance in `[0, 2]`, or `1.0 / (1.0 + distance)` fallback for non-cosine/legacy collections)
     and applies a conservative configurable `min_relevance` threshold.
   - Note on Calibration: `relevance_score` is a monotonically decreasing function of vector distance
     used for ranking and threshold filtering — it is NOT a calibrated probability. Thresholds should be
     calibrated empirically against the Jeevan Setu clinical retrieval evaluation dataset.
3. Citation & Traceability (`extract_source_references`):
   - Every returned chunk dictionary contains `chunk_id`, `document_id`, `document_version`, `content`,
     `source`, `category`, `file_type`, `page_number` (when available, never fabricated), `chunk_index`,
     `distance`, `relevance_score`, `image_assets`, and `metadata`.
4. Clinical & Collection Security:
   - Restricts searches strictly to the approved shared knowledge collection (`jeevan_setu_knowledge`).
   - Rejects user/caller attempts to query arbitrary or patient-specific collections.
   - Filters out any record containing identifiable patient `UHID-YYYY-NNNNN` markers or `patient_id` fields.
   - Never logs full clinical queries or retrieved document content.
"""

import copy
import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from chatbot.rag.embedding_service import (
    EXPECTED_EMBEDDING_DIMENSION,
    get_embedding,
)
from chatbot.rag.vector_store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_DOCUMENT_VERSION,
    UHID_PATTERN,
    VectorStore,
    validate_embedding_vector,
)

logger = logging.getLogger("jeevan_setu.rag.retriever")

DEFAULT_TOP_K = 5
MAX_TOP_K = 50

# Conservative default minimum relevance score (in [0.0, 1.0]).
# For cosine distance d in [0, 2], relevance_score = max(0.0, 1.0 - d / 2.0).
# A default of 0.25 corresponds to cosine distance <= 1.50, filtering out orthogonal/opposite noise
# while retaining relevant clinical protocol chunks. Should be calibrated on evaluation benchmarks.
DEFAULT_MIN_RELEVANCE_SCORE = 0.25

ALLOWED_FILE_TYPES = frozenset({
    "pdf",
    "docx",
    "txt",
    "markdown",
    "md",
    "json",
})

# Safe identifier pattern for filter values (prevents injection of operators like `$where` or `$ne`)
SAFE_FILTER_VALUE_RE = re.compile(r"^[A-Za-z0-9_./:\- ]{1,128}$")

PROHIBITED_PATIENT_KEYS = frozenset({
    "patient_id",
    "patient_image_id",
    "patient_name",
    "uhid",
})


def embed_query(query: str) -> List[float]:
    """
    Validate a user search query and generate its 384-dimensional embedding vector
    using `get_embedding()` from `chatbot/rag/embedding_service.py`.

    Raises:
        ValueError: If `query` is not a non-empty string or if the resulting embedding
                    does not have 384 finite float values.
    """
    if not isinstance(query, str):
        raise ValueError(f"Search query must be a str, got {type(query).__name__}.")
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Search query must be a non-empty, non-whitespace string.")

    raw_vec = get_embedding(cleaned)
    return validate_embedding_vector(raw_vec, EXPECTED_EMBEDDING_DIMENSION)


def _validate_top_k(top_k: int) -> int:
    """Validate `top_k` is a positive integer within safe bounds."""
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")
    return min(top_k, MAX_TOP_K)


def _validate_min_relevance(min_relevance: Optional[float]) -> float:
    """Validate `min_relevance` is a finite number in `[0.0, 1.0]`."""
    if min_relevance is None:
        return DEFAULT_MIN_RELEVANCE_SCORE
    if isinstance(min_relevance, bool) or not isinstance(min_relevance, (int, float)):
        raise ValueError("min_relevance must be a numeric value between 0.0 and 1.0.")
    val = float(min_relevance)
    if not math.isfinite(val) or val < 0.0 or val > 1.0:
        raise ValueError("min_relevance must be a finite number between 0.0 and 1.0.")
    return val


def _validate_filter_string(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate an optional string filter parameter."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Filter '{field_name}' must be a string, got {type(value).__name__}.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Filter '{field_name}' cannot be an empty or whitespace-only string.")
    if cleaned.startswith("$") or not SAFE_FILTER_VALUE_RE.match(cleaned):
        raise ValueError(f"Filter '{field_name}' contains invalid characters.")
    if UHID_PATTERN.search(cleaned):
        raise ValueError(f"Filter '{field_name}' must not contain a patient UHID identifier.")
    return cleaned


def build_metadata_where_clause(
    category: Optional[str] = None,
    document_id: Optional[str] = None,
    file_type: Optional[str] = None,
    document_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Validate optional metadata filter parameters and construct a ChromaDB-compatible `where` dictionary.

    Raises:
        ValueError: If any provided filter value is malformed or unsupported.
    """
    clauses: List[Dict[str, Any]] = []

    cat_val = _validate_filter_string(category, "category")
    if cat_val is not None:
        clauses.append({"category": cat_val})

    doc_id_val = _validate_filter_string(document_id, "document_id")
    if doc_id_val is not None:
        clauses.append({"document_id": doc_id_val})

    ft_val = _validate_filter_string(file_type, "file_type")
    if ft_val is not None:
        ft_norm = ft_val.lower().lstrip(".")
        if ft_norm not in ALLOWED_FILE_TYPES:
            raise ValueError(
                f"Unsupported file_type filter '{file_type}'. Allowed values: {sorted(ALLOWED_FILE_TYPES)}."
            )
        if ft_norm == "md":
            ft_norm = "markdown"
        clauses.append({"file_type": ft_norm})

    ver_val = _validate_filter_string(document_version, "document_version")
    if ver_val is not None:
        clauses.append({"document_version": ver_val})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def distance_to_relevance_score(
    distance: Optional[float],
    similarity_metric: str = "cosine",
) -> float:
    """
    Convert a ChromaDB distance value into a normalized monotonic relevance score in `[0.0, 1.0]`.

    - For cosine distance (`d = 1 - cos_sim`, where `d` is in `[0.0, 2.0]`):
      `relevance_score = clamp(1.0 - d / 2.0, 0.0, 1.0)`.
      (`d = 0.0` -> `1.0`, `d = 1.0` -> `0.5`, `d >= 2.0` -> `0.0`).
    - For L2 / squared Euclidean distance (`d >= 0.0`):
      `relevance_score = 1.0 / (1.0 + d)`.
    - If `distance` is `None` or non-finite, returns `0.0` safely.

    Note: This score is a deterministic similarity ranking metric, not a calibrated probability.
    """
    if distance is None or isinstance(distance, bool) or not isinstance(distance, (int, float)):
        return 0.0
    d = float(distance)
    if not math.isfinite(d):
        return 0.0
    if d < 0.0:
        d = 0.0

    metric = str(similarity_metric or "cosine").strip().lower()
    if metric == "cosine":
        score = max(0.0, min(1.0, 1.0 - (d / 2.0)))
    else:
        score = 1.0 / (1.0 + d)
    return round(score, 6)


def _is_patient_contaminated_record(content: str, metadata: Dict[str, Any]) -> bool:
    """Return True if a chunk record contains identifiable patient data or patient-specific image fields."""
    if UHID_PATTERN.search(content or ""):
        return True
    for k, v in (metadata or {}).items():
        if str(k).lower() in PROHIBITED_PATIENT_KEYS and v is not None:
            return True
        if isinstance(v, str) and UHID_PATTERN.search(v):
            return True
    return False


def _extract_image_assets_from_record(raw_item: Dict[str, Any], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and sanitize image asset reference dictionaries without fabricating fields."""
    raw_assets = raw_item.get("image_assets")
    if not isinstance(raw_assets, list):
        raw_json = metadata.get("image_assets_json")
        if isinstance(raw_json, str) and raw_json.strip():
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, list):
                    raw_assets = parsed
            except Exception:
                raw_assets = []
        else:
            raw_assets = []

    clean_assets: List[Dict[str, Any]] = []
    for asset in raw_assets or []:
        if not isinstance(asset, dict):
            continue
        if any(k in asset for k in PROHIBITED_PATIENT_KEYS):
            continue
        asset_path = asset.get("asset_path")
        image_id = asset.get("image_id")
        if not isinstance(asset_path, str) or not asset_path.strip():
            continue
        clean_assets.append(copy.deepcopy(asset))
    return clean_assets


def _normalize_retrieved_chunk(
    raw_item: Dict[str, Any],
    similarity_metric: str = "cosine",
) -> Optional[Dict[str, Any]]:
    """
    Normalize a raw item from `VectorStore` into the canonical retriever result dictionary.
    Never fabricates missing page numbers, titles, or citations.
    Returns `None` if the item is empty or fails patient-isolation guardrails.
    """
    if not isinstance(raw_item, dict):
        return None

    content = str(raw_item.get("content") or raw_item.get("document") or "").strip()
    if not content:
        return None

    raw_meta = raw_item.get("metadata")
    meta: Dict[str, Any] = copy.deepcopy(raw_meta) if isinstance(raw_meta, dict) else {}

    if _is_patient_contaminated_record(content, meta):
        logger.warning("Filtered out chunk failing patient-isolation check.")
        return None

    chunk_id = str(
        raw_item.get("chunk_id")
        or meta.get("chunk_id")
        or raw_item.get("id")
        or ""
    ).strip()
    if not chunk_id:
        return None

    source = str(
        raw_item.get("source")
        or meta.get("source")
        or "unknown"
    ).strip() or "unknown"

    category = str(
        raw_item.get("category")
        or meta.get("category")
        or "general"
    ).strip() or "general"

    file_type = str(
        raw_item.get("file_type")
        or meta.get("file_type")
        or (Path(source).suffix.lower().lstrip(".") if Path(source).suffix else "txt")
    ).strip().lower() or "txt"
    if file_type == "md":
        file_type = "markdown"

    # Never fabricate page_number: preserve only if a valid positive integer exists
    raw_page = raw_item.get("page_number") if "page_number" in raw_item and raw_item.get("page_number") is not None else meta.get("page_number")
    page_number: Optional[int] = None
    if file_type != "docx" and isinstance(raw_page, int) and not isinstance(raw_page, bool) and raw_page >= 1:
        page_number = raw_page

    document_id = (
        raw_item.get("document_id")
        or meta.get("document_id")
        or None
    )
    if isinstance(document_id, str):
        document_id = document_id.strip() or None

    raw_version = (
        raw_item.get("document_version")
        or meta.get("document_version")
        or meta.get("version")
        or DEFAULT_DOCUMENT_VERSION
    )
    document_version = str(raw_version).strip() if raw_version is not None and str(raw_version).strip() else DEFAULT_DOCUMENT_VERSION

    raw_cidx = raw_item.get("chunk_index") if "chunk_index" in raw_item and raw_item.get("chunk_index") is not None else meta.get("chunk_index", 0)
    chunk_index = int(raw_cidx) if isinstance(raw_cidx, (int, float)) and not isinstance(raw_cidx, bool) else 0

    raw_dist = raw_item.get("distance")
    has_valid_dist = (
        raw_dist is not None
        and not isinstance(raw_dist, bool)
        and isinstance(raw_dist, (int, float))
        and math.isfinite(float(raw_dist))
    )
    distance_val: Optional[float] = round(float(raw_dist), 6) if has_valid_dist else None
    relevance_score = distance_to_relevance_score(distance_val, similarity_metric=similarity_metric) if has_valid_dist else 0.0

    image_assets = _extract_image_assets_from_record(raw_item, meta)

    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "document_version": document_version,
        "content": content,
        "source": source,
        "category": category,
        "file_type": file_type,
        "page_number": page_number,
        "chunk_index": chunk_index,
        "distance": distance_val,
        "relevance_score": relevance_score,
        "score": relevance_score,
        "image_assets": image_assets,
        "metadata": meta,
    }


def _resolve_safe_vector_store(
    store: Optional[VectorStore] = None,
    storage_dir: Optional[Union[str, Path]] = None,
) -> VectorStore:
    """
    Return the provided `VectorStore` instance or initialize one pointing to the approved
    shared knowledge collection (`jeevan_setu_knowledge`).
    Rejects stores configured with prohibited patient-specific collection names.
    """
    if store is not None:
        if not isinstance(store, VectorStore):
            raise ValueError(f"Expected 'store' to be a VectorStore instance, got {type(store).__name__}.")
        col_name_lower = str(getattr(store, "collection_name", "")).lower()
        if "patient" in col_name_lower or UHID_PATTERN.search(col_name_lower):
            raise ValueError("Retriever is restricted to the shared knowledge collection and cannot query patient collections.")
        return store
    return VectorStore(storage_dir=storage_dir, collection_name=DEFAULT_COLLECTION_NAME)


def retrieve_relevant_chunks(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    store: Optional[VectorStore] = None,
    *,
    category: Optional[str] = None,
    document_id: Optional[str] = None,
    file_type: Optional[str] = None,
    document_version: Optional[str] = None,
    min_relevance: Optional[float] = DEFAULT_MIN_RELEVANCE_SCORE,
    storage_dir: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve the top-k most relevant knowledge-base chunks for a query using 384-d semantic search.

    Args:
        query: Non-empty user search query string.
        top_k: Maximum number of relevant chunks to return (default: 5, max: 50).
        store: Optional pre-initialized `VectorStore` instance (e.g., for isolated testing).
        category: Optional knowledge category filter (`clinical_protocols`, `hospital_sops`, etc.).
        document_id: Optional stable document identifier filter.
        file_type: Optional file type filter (`pdf`, `docx`, `txt`, `markdown`, `json`).
        document_version: Optional document version filter (e.g., `"1.0"`).
        min_relevance: Minimum normalized relevance score in `[0.0, 1.0]` (default: 0.25).
        storage_dir: Optional storage directory override for `VectorStore`.

    Returns:
        Deterministic list of deduplicated result dictionaries ordered by descending
        `relevance_score` (and ascending `distance`, then `chunk_id` as tie-breaker).
    """
    validated_k = _validate_top_k(top_k)
    validated_min_rel = _validate_min_relevance(min_relevance)
    where_clause = build_metadata_where_clause(
        category=category,
        document_id=document_id,
        file_type=file_type,
        document_version=document_version,
    )

    # Generate and validate the 384-d query vector using embedding_service.get_embedding()
    query_embedding = embed_query(query)

    try:
        vs = _resolve_safe_vector_store(store=store, storage_dir=storage_dir)
        collection = vs.get_or_create_collection()
        total_count = int(collection.count())
        if total_count == 0:
            return []

        col_meta = dict(collection.metadata or {})
        similarity_metric = str(col_meta.get("hnsw:space", "cosine"))

        # Fetch a slightly wider candidate pool before deduplication and threshold filtering
        candidate_k = min(total_count, max(validated_k * 2, validated_k))
        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": candidate_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_clause is not None:
            query_kwargs["where"] = where_clause

        raw = collection.query(**query_kwargs)
    except ValueError:
        raise
    except Exception as exc:
        logger.error("ChromaDB retrieval failed safely: %s", type(exc).__name__)
        return []

    ids_list = (raw.get("ids") or [[]])[0]
    docs_list = (raw.get("documents") or [[]])[0]
    metas_list = (raw.get("metadatas") or [[]])[0]
    dists_list = (raw.get("distances") or [[]])[0]

    deduped_results: List[Dict[str, Any]] = []
    seen_chunk_ids: Set[str] = set()
    seen_content_hashes: Set[str] = set()

    for idx, cid in enumerate(ids_list):
        doc_text = docs_list[idx] if idx < len(docs_list) else ""
        meta = metas_list[idx] if idx < len(metas_list) and metas_list[idx] is not None else {}
        dist = dists_list[idx] if idx < len(dists_list) else None

        raw_item = {
            "id": cid,
            "chunk_id": meta.get("chunk_id") or cid,
            "content": doc_text,
            "metadata": meta,
            "distance": dist,
        }
        normalized = _normalize_retrieved_chunk(raw_item, similarity_metric=similarity_metric)
        if normalized is None:
            continue

        # Enforce post-retrieval metadata match as a secondary safeguard
        if category is not None and normalized["category"] != category.strip():
            continue
        if document_id is not None and normalized["document_id"] != document_id.strip():
            continue
        if file_type is not None:
            norm_ft = file_type.strip().lower().lstrip(".")
            if norm_ft == "md":
                norm_ft = "markdown"
            if normalized["file_type"] != norm_ft:
                continue
        if document_version is not None and normalized["document_version"] != document_version.strip():
            continue

        # Apply minimum relevance threshold
        if normalized["relevance_score"] < validated_min_rel:
            continue

        # Deduplicate by chunk_id and by exact content_hash (or content text)
        norm_cid = normalized["chunk_id"]
        c_hash = str(normalized["metadata"].get("content_hash") or normalized["content"])
        if norm_cid in seen_chunk_ids or c_hash in seen_content_hashes:
            continue
        seen_chunk_ids.add(norm_cid)
        seen_content_hashes.add(c_hash)
        deduped_results.append(normalized)

    # Deterministic ordering: highest relevance_score first, lowest distance second, chunk_index, chunk_id
    deduped_results.sort(
        key=lambda r: (
            -float(r["relevance_score"]),
            float(r["distance"]) if r["distance"] is not None else float("inf"),
            int(r["chunk_index"]),
            str(r["chunk_id"]),
        )
    )

    return deduped_results[:validated_k]


def retrieve_with_filters(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    category: Optional[str] = None,
    document_id: Optional[str] = None,
    file_type: Optional[str] = None,
    document_version: Optional[str] = None,
    min_relevance: Optional[float] = DEFAULT_MIN_RELEVANCE_SCORE,
    store: Optional[VectorStore] = None,
    storage_dir: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience wrapper to retrieve relevant chunks with explicit metadata filters.
    """
    return retrieve_relevant_chunks(
        query=query,
        top_k=top_k,
        store=store,
        category=category,
        document_id=document_id,
        file_type=file_type,
        document_version=document_version,
        min_relevance=min_relevance,
        storage_dir=storage_dir,
    )


def retrieve_by_document_id(
    document_id: str,
    query: Optional[str] = None,
    document_version: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    min_relevance: Optional[float] = 0.0,
    store: Optional[VectorStore] = None,
    storage_dir: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve chunks belonging to a specific `document_id` (and optional `document_version`).
    - When `query` is provided, performs semantic retrieval within that document.
    - When `query` is `None`, retrieves the document's chunks ordered by `chunk_index` ASC.
    """
    clean_doc_id = _validate_filter_string(document_id, "document_id")
    if clean_doc_id is None:
        raise ValueError("document_id must be a non-empty string.")
    clean_ver = _validate_filter_string(document_version, "document_version")
    validated_k = _validate_top_k(top_k)

    if query is not None:
        return retrieve_relevant_chunks(
            query=query,
            top_k=validated_k,
            store=store,
            document_id=clean_doc_id,
            document_version=clean_ver,
            min_relevance=min_relevance,
            storage_dir=storage_dir,
        )

    try:
        vs = _resolve_safe_vector_store(store=store, storage_dir=storage_dir)
        collection = vs.get_or_create_collection()
        if int(collection.count()) == 0:
            return []

        where_clause = build_metadata_where_clause(
            document_id=clean_doc_id,
            document_version=clean_ver,
        )
        raw = collection.get(where=where_clause, include=["documents", "metadatas"])
    except ValueError:
        raise
    except Exception as exc:
        logger.error("ChromaDB document chunk lookup failed safely: %s", type(exc).__name__)
        return []

    ids_list = raw.get("ids") or []
    docs_list = raw.get("documents") or []
    metas_list = raw.get("metadatas") or []

    results: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    for idx, cid in enumerate(ids_list):
        doc_text = docs_list[idx] if idx < len(docs_list) else ""
        meta = metas_list[idx] if idx < len(metas_list) and metas_list[idx] is not None else {}
        norm = _normalize_retrieved_chunk(
            {
                "id": cid,
                "chunk_id": meta.get("chunk_id") or cid,
                "content": doc_text,
                "metadata": meta,
                "distance": 0.0,
            }
        )
        if norm is None or norm["chunk_id"] in seen_ids:
            continue
        if norm["document_id"] != clean_doc_id:
            continue
        if clean_ver is not None and norm["document_version"] != clean_ver:
            continue
        seen_ids.add(norm["chunk_id"])
        results.append(norm)

    results.sort(key=lambda r: (int(r["chunk_index"]), str(r["chunk_id"])))
    return results[:validated_k]


def retrieve_multiple_queries(
    queries: Sequence[str],
    top_k_per_query: int = DEFAULT_TOP_K,
    max_total_results: Optional[int] = None,
    category: Optional[str] = None,
    document_id: Optional[str] = None,
    file_type: Optional[str] = None,
    document_version: Optional[str] = None,
    min_relevance: Optional[float] = DEFAULT_MIN_RELEVANCE_SCORE,
    store: Optional[VectorStore] = None,
    storage_dir: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Execute semantic retrieval across multiple queries, deduplicating chunks across queries
    while keeping the highest `relevance_score` observed for each unique chunk.
    """
    if not isinstance(queries, (list, tuple)) or len(queries) == 0:
        raise ValueError("queries must be a non-empty list or tuple of query strings.")

    merged_by_id: Dict[str, Dict[str, Any]] = {}
    seen_content_keys: Dict[str, str] = {}

    for q in queries:
        hits = retrieve_relevant_chunks(
            query=q,
            top_k=top_k_per_query,
            store=store,
            category=category,
            document_id=document_id,
            file_type=file_type,
            document_version=document_version,
            min_relevance=min_relevance,
            storage_dir=storage_dir,
        )
        for hit in hits:
            cid = hit["chunk_id"]
            c_key = str(hit["metadata"].get("content_hash") or hit["content"])
            existing_cid = seen_content_keys.get(c_key, cid)
            if existing_cid not in merged_by_id or hit["relevance_score"] > merged_by_id[existing_cid]["relevance_score"]:
                merged_by_id[existing_cid] = hit
                seen_content_keys[c_key] = existing_cid

    combined = list(merged_by_id.values())
    combined.sort(
        key=lambda r: (
            -float(r["relevance_score"]),
            float(r["distance"]) if r["distance"] is not None else float("inf"),
            int(r["chunk_index"]),
            str(r["chunk_id"]),
        )
    )
    if max_total_results is not None:
        limit = _validate_top_k(max_total_results)
        return combined[:limit]
    return combined


def extract_source_references(chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a structured list of citation/source reference dictionaries from retrieved chunks
    without fabricating titles, page numbers, or citations.
    """
    if not chunks or not isinstance(chunks, (list, tuple)):
        return []

    references: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, Optional[int], str]] = set()

    for ch in chunks:
        if not isinstance(ch, dict):
            continue
        chunk_id = str(ch.get("chunk_id") or "").strip()
        source = str(ch.get("source") or "unknown").strip()
        if not chunk_id or not source:
            continue
        page_num = ch.get("page_number")
        valid_page = int(page_num) if isinstance(page_num, int) and not isinstance(page_num, bool) and page_num >= 1 else None
        doc_ver = str(ch.get("document_version") or DEFAULT_DOCUMENT_VERSION)

        dedup_key = (chunk_id, valid_page, doc_ver)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        citation_str = f"{source} (p. {valid_page})" if valid_page is not None else source
        ref: Dict[str, Any] = {
            "chunk_id": chunk_id,
            "document_id": ch.get("document_id"),
            "document_version": doc_ver,
            "source": source,
            "category": ch.get("category", "general"),
            "file_type": ch.get("file_type", "txt"),
            "page_number": valid_page,
            "chunk_index": ch.get("chunk_index", 0),
            "relevance_score": ch.get("relevance_score", 0.0),
            "citation": citation_str,
            "image_assets": copy.deepcopy(ch.get("image_assets") or []),
        }
        references.append(ref)

    return references
