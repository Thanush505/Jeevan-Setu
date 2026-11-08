"""
chatbot/tools/__init__.py

Public exports for Jeevan Setu Agentic Hybrid RAG Tool Layer.
"""

from chatbot.tools.chroma_knowledge_tools import (
    get_document_source,
    search_approved_guidelines,
    search_clinical_protocols,
    search_hospital_sops,
    search_knowledge_base,
)
from chatbot.tools.mysql_patient_tools import (
    get_patient_alerts,
    get_patient_bed_and_ward_details,
    get_patient_clinical_notes,
    get_patient_ews,
    get_patient_recommendations,
    get_patient_summary,
    get_patient_transfer_history,
    get_patient_vitals,
)
from chatbot.tools.tool_executor import (
    execute_tool_call,
    parse_openrouter_tool_calls,
    parse_structured_tool_call_fallback,
    run_agentic_rag_workflow,
)
from chatbot.tools.tool_registry import (
    ToolDefinition,
    ToolRegistry,
    get_default_tool_registry,
)

__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "get_default_tool_registry",
    "execute_tool_call",
    "parse_openrouter_tool_calls",
    "parse_structured_tool_call_fallback",
    "run_agentic_rag_workflow",
    "get_patient_summary",
    "get_patient_vitals",
    "get_patient_ews",
    "get_patient_recommendations",
    "get_patient_transfer_history",
    "get_patient_clinical_notes",
    "get_patient_alerts",
    "get_patient_bed_and_ward_details",
    "search_knowledge_base",
    "search_clinical_protocols",
    "search_hospital_sops",
    "search_approved_guidelines",
    "get_document_source",
]

