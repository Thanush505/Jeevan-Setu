"""
chatbot/tools/chroma_knowledge_tools.py

Approved ChromaDB knowledge-base tools for Jeevan Setu Agentic Hybrid RAG.

Uses the existing `chatbot/rag/retriever.py` and the shared `jeevan_setu_knowledge`
ChromaDB collection without creating duplicate embedding or vector services.

Security & Traceability Guarantees:
1. Preserves `document_id`, `page_number`, `chunk_id`, `document_version`,
   `source`, `category`, and `relevance_score` across all returned chunks.
2. Never retrieves or exposes patient-specific records or UHID patterns from
   the shared knowledge collection.
3. Sanitizes all retrieved document content via `sanitize_untrusted_text` so
   untrusted document instructions cannot override system or RBAC rules.
4. Safe for both Patient Chat (`chat_mode="patient"`) and General Chat
   (`chat_mode="general"`).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from chatbot.rag.context_builder import sanitize_untrusted_text
from chatbot.rag.retriever import (
    DEFAULT_MIN_RELEVANCE_SCORE,
    DEFAULT_TOP_K,
    extract_source_references,
    retrieve_by_document_id,
    retrieve_relevant_chunks,
    retrieve_with_filters,
)
from chatbot.rag.vector_store import UHID_PATTERN, VectorStore

logger = logging.getLogger("jeevan_setu.tools.chroma_knowledge")

MAX_TOOL_TOP_K = 20


def _validate_search_query(query: Any) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must be a non-empty string.")
    cleaned = query.strip()
    if UHID_PATTERN.search(cleaned):
        raise ValueError(
            "Shared ChromaDB knowledge tools cannot be queried with patient-identifiable UHID markers."
        )
    return cleaned


def _clamp_top_k(top_k: Any) -> int:
    if top_k is None or isinstance(top_k, bool):
        return DEFAULT_TOP_K
    try:
        val = int(top_k)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid top_k '{top_k}': must be an integer.") from exc
    return max(1, min(val, MAX_TOOL_TOP_K))


def _validate_min_relevance(min_relevance: Any) -> float:
    if min_relevance is None or isinstance(min_relevance, bool):
        return DEFAULT_MIN_RELEVANCE_SCORE
    try:
        val = float(min_relevance)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid min_relevance '{min_relevance}': must be a float.") from exc
    return max(0.0, min(val, 1.0))


def _format_and_sanitize_chunks(
    raw_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Sanitize chunk content, enforce UHID/patient-record filtering, and preserve
    all source traceability metadata (`document_id`, `page_number`, `chunk_id`,
    `document_version`, `source`, `category`, `relevance_score`).
    """
    sanitized_chunks: List[Dict[str, Any]] = []
    security_warnings: List[str] = []
    seen_chunk_ids = set()

    for idx, c in enumerate(raw_chunks or []):
        if not isinstance(c, dict):
            continue
        raw_content = c.get("content") or c.get("document") or ""
        if not isinstance(raw_content, str) or not raw_content.strip():
            continue

        meta = c.get("metadata") if isinstance(c.get("metadata"), dict) else {}

        # Never return any chunk containing patient UHID or patient_id metadata
        if (
            UHID_PATTERN.search(raw_content)
            or "patient_id" in meta
            or "patient_id" in c
        ):
            continue

        chunk_id = str(c.get("chunk_id") or meta.get("chunk_id") or f"chunk_{idx}")
        if chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)

        clean_content, warns = sanitize_untrusted_text(raw_content)
        security_warnings.extend(warns)
        if not clean_content:
            continue
        document_id = str(c.get("document_id") or meta.get("document_id") or "UNKNOWN_DOC")
        source = str(c.get("source") or meta.get("source") or "unknown_source")
        category = str(c.get("category") or meta.get("category") or "general")
        document_version = str(c.get("document_version") or meta.get("document_version") or "1.0")
        page_number = c.get("page_number") if c.get("page_number") is not None else meta.get("page_number", 1)
        try:
            page_number = max(1, int(page_number))
        except (ValueError, TypeError):
            page_number = 1

        rel_score = c.get("relevance_score")
        if rel_score is None:
            rel_score = meta.get("relevance_score", 0.0)
        try:
            rel_score = round(float(rel_score), 6)
        except (ValueError, TypeError):
            rel_score = 0.0

        sanitized_chunks.append({
            "chunk_id": chunk_id,
            "document_id": document_id,
            "source": source,
            "category": category,
            "page_number": page_number,
            "document_version": document_version,
            "content": clean_content,
            "relevance_score": rel_score,
            "image_assets": c.get("image_assets") or [],
            "metadata": {
                **meta,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source": source,
                "category": category,
                "page_number": page_number,
                "document_version": document_version,
            },
        })

    sources = extract_source_references(sanitized_chunks)
    return {
        "chunks": sanitized_chunks,
        "sources": sources,
        "count": len(sanitized_chunks),
        "security_warnings": security_warnings,
    }


# =============================================================================
# 1. search_knowledge_base
# =============================================================================

def search_knowledge_base(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    category: Optional[str] = None,
    min_relevance: float = DEFAULT_MIN_RELEVANCE_SCORE,
    *,
    store: Optional[VectorStore] = None,
    retriever_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search the shared `jeevan_setu_knowledge` ChromaDB collection for relevant
    clinical, protocol, SOP, or educational reference chunks.
    """
    clean_q = _validate_search_query(query)
    safe_k = _clamp_top_k(top_k)
    safe_min_rel = _validate_min_relevance(min_relevance)

    active_retriever = retriever_fn or retrieve_relevant_chunks
    raw_chunks = active_retriever(
        query=clean_q,
        top_k=safe_k,
        store=store,
        category=category,
        min_relevance=safe_min_rel,
    )

    formatted = _format_and_sanitize_chunks(raw_chunks)
    return {
        "tool": "search_knowledge_base",
        "query": clean_q,
        "category_filter": category,
        "chunks": formatted["chunks"],
        "sources": formatted["sources"],
        "count": formatted["count"],
        "security_warnings": formatted["security_warnings"],
        "collection": "jeevan_setu_knowledge",
    }


# =============================================================================
# 2. search_clinical_protocols
# =============================================================================

def search_clinical_protocols(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_relevance: float = DEFAULT_MIN_RELEVANCE_SCORE,
    *,
    store: Optional[VectorStore] = None,
    retriever_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search clinical protocols (e.g., EWS scoring protocols, deterioration
    escalation, sepsis/respiratory management protocols) in ChromaDB.
    """
    clean_q = _validate_search_query(query)
    safe_k = _clamp_top_k(top_k)
    safe_min_rel = _validate_min_relevance(min_relevance)

    active_retriever = retriever_fn or retrieve_with_filters
    raw_chunks: List[Dict[str, Any]] = []

    for candidate_cat in ("clinical_protocols", "ews_protocols", "protocols", "protocol"):
        try:
            res = active_retriever(
                query=clean_q,
                top_k=safe_k,
                store=store,
                category=candidate_cat,
                min_relevance=safe_min_rel,
            )
            if res:
                raw_chunks.extend(res)
                if len(raw_chunks) >= safe_k:
                    break
        except Exception:
            continue

    # Fallback to broad knowledge base search if documents were indexed under general category
    if not raw_chunks:
        fallback_fn = retriever_fn or retrieve_relevant_chunks
        raw_chunks = fallback_fn(
            query=clean_q,
            top_k=safe_k,
            store=store,
            min_relevance=safe_min_rel,
        )

    formatted = _format_and_sanitize_chunks(raw_chunks[:safe_k])
    return {
        "tool": "search_clinical_protocols",
        "query": clean_q,
        "chunks": formatted["chunks"],
        "sources": formatted["sources"],
        "count": formatted["count"],
        "security_warnings": formatted["security_warnings"],
        "collection": "jeevan_setu_knowledge",
    }


# =============================================================================
# 3. search_hospital_sops
# =============================================================================

def search_hospital_sops(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_relevance: float = DEFAULT_MIN_RELEVANCE_SCORE,
    *,
    store: Optional[VectorStore] = None,
    retriever_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search hospital Standard Operating Procedures (SOPs) for ICU/HDU handoff,
    bed allocation workflows, and nursing/command-center escalation procedures.
    """
    clean_q = _validate_search_query(query)
    safe_k = _clamp_top_k(top_k)
    safe_min_rel = _validate_min_relevance(min_relevance)

    active_retriever = retriever_fn or retrieve_with_filters
    raw_chunks: List[Dict[str, Any]] = []

    for candidate_cat in ("hospital_sops", "sop", "sops", "operations"):
        try:
            res = active_retriever(
                query=clean_q,
                top_k=safe_k,
                store=store,
                category=candidate_cat,
                min_relevance=safe_min_rel,
            )
            if res:
                raw_chunks.extend(res)
                if len(raw_chunks) >= safe_k:
                    break
        except Exception:
            continue

    if not raw_chunks:
        fallback_fn = retriever_fn or retrieve_relevant_chunks
        raw_chunks = fallback_fn(
            query=clean_q,
            top_k=safe_k,
            store=store,
            min_relevance=safe_min_rel,
        )

    formatted = _format_and_sanitize_chunks(raw_chunks[:safe_k])
    return {
        "tool": "search_hospital_sops",
        "query": clean_q,
        "chunks": formatted["chunks"],
        "sources": formatted["sources"],
        "count": formatted["count"],
        "security_warnings": formatted["security_warnings"],
        "collection": "jeevan_setu_knowledge",
    }


# =============================================================================
# 4. search_approved_guidelines
# =============================================================================

def search_approved_guidelines(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_relevance: float = DEFAULT_MIN_RELEVANCE_SCORE,
    *,
    store: Optional[VectorStore] = None,
    retriever_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Search approved ICU <-> HDU transfer eligibility guidelines and clinical
    step-down/step-up criteria in ChromaDB.
    """
    clean_q = _validate_search_query(query)
    safe_k = _clamp_top_k(top_k)
    safe_min_rel = _validate_min_relevance(min_relevance)

    active_retriever = retriever_fn or retrieve_with_filters
    raw_chunks: List[Dict[str, Any]] = []

    for candidate_cat in ("transfer_guidelines", "clinical_guidelines", "guidelines", "guideline"):
        try:
            res = active_retriever(
                query=clean_q,
                top_k=safe_k,
                store=store,
                category=candidate_cat,
                min_relevance=safe_min_rel,
            )
            if res:
                raw_chunks.extend(res)
                if len(raw_chunks) >= safe_k:
                    break
        except Exception:
            continue

    if not raw_chunks:
        fallback_fn = retriever_fn or retrieve_relevant_chunks
        raw_chunks = fallback_fn(
            query=clean_q,
            top_k=safe_k,
            store=store,
            min_relevance=safe_min_rel,
        )

    formatted = _format_and_sanitize_chunks(raw_chunks[:safe_k])
    return {
        "tool": "search_approved_guidelines",
        "query": clean_q,
        "chunks": formatted["chunks"],
        "sources": formatted["sources"],
        "count": formatted["count"],
        "security_warnings": formatted["security_warnings"],
        "collection": "jeevan_setu_knowledge",
    }


# =============================================================================
# 5. get_document_source
# =============================================================================

def get_document_source(
    document_id: str,
    document_version: Optional[str] = None,
    top_k: int = 10,
    *,
    store: Optional[VectorStore] = None,
    doc_retriever_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Retrieve indexed chunks and full source provenance metadata (`document_id`,
    `source`, `category`, `page_number`, `chunk_id`, `document_version`) for a
    specific knowledge-base document.
    """
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("document_id must be a non-empty string.")
    clean_doc_id = document_id.strip()
    if UHID_PATTERN.search(clean_doc_id):
        raise ValueError("document_id cannot reference a patient UHID.")

    safe_k = _clamp_top_k(top_k)
    active_doc_retriever = doc_retriever_fn or retrieve_by_document_id
    raw_chunks = active_doc_retriever(
        document_id=clean_doc_id,
        store=store,
        document_version=document_version,
        top_k=safe_k,
    )

    formatted = _format_and_sanitize_chunks(raw_chunks)
    return {
        "tool": "get_document_source",
        "document_id": clean_doc_id,
        "document_version": document_version,
        "found": formatted["count"] > 0,
        "chunks": formatted["chunks"],
        "sources": formatted["sources"],
        "count": formatted["count"],
        "security_warnings": formatted["security_warnings"],
        "collection": "jeevan_setu_knowledge",
    }


__all__ = [
    "search_knowledge_base",
    "search_clinical_protocols",
    "search_hospital_sops",
    "search_approved_guidelines",
    "get_document_source",
]
