"""
chatbot/tools/tool_registry.py

Central allowlisted Tool Registry for Jeevan Setu Agentic Hybrid RAG.

Every registered tool defines:
- `name`: Unique allowlisted tool name
- `description`: Purpose and scope of the tool
- `input_schema`: OpenAI/OpenRouter-compatible JSON Schema
- `required_arguments`: Tuple of mandatory parameter names
- `argument_types`: Mapping of argument name to expected Python type(s)
- `authorization_requirements`: Dict specifying `requires_auth`, `allowed_roles`,
  `requires_patient_auth`, and `source_type` ("mysql_patient" or "chroma_knowledge")
- `allowed_chat_modes`: Tuple of permitted chat modes ("patient", "general")
- `execution_fn`: Bound Python function from `mysql_patient_tools` or `chroma_knowledge_tools`

Security Rules:
1. Strict allowlist: unknown tool names are always rejected.
2. Strict chat-mode isolation: when `chat_mode == "general"`, MySQL patient
   tools are NEVER included in tool definitions and are ALWAYS rejected if
   requested.
3. Strict argument validation: unexpected arguments, missing required arguments,
   wrong types, invalid patient IDs, or embedded SQL/code-execution patterns are
   rejected before execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

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

ALL_CLINICAL_ROLES: Tuple[str, ...] = (
    "admin",
    "superadmin",
    "doctor",
    "nurse",
    "command_center",
    "attendant",
)

STAFF_ONLY_ROLES: Tuple[str, ...] = (
    "admin",
    "superadmin",
    "doctor",
    "nurse",
    "command_center",
)

# Disallowed SQL / code execution patterns inside string tool arguments
_UNSAFE_ARG_PATTERN = re.compile(
    r"(?:;\s*(?:select|insert|update|delete|drop|alter|truncate|create|grant|revoke)\b|"
    r"\b(?:union\s+select|drop\s+table|delete\s+from|insert\s+into|update\s+\w+\s+set|"
    r"xp_cmdshell|information_schema|sleep\s*\(|benchmark\s*\(|__import__|eval\s*\(|exec\s*\()\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable metadata and execution contract for a single allowlisted tool."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    required_arguments: Tuple[str, ...]
    argument_types: Dict[str, Union[Type, Tuple[Type, ...]]]
    authorization_requirements: Dict[str, Any]
    allowed_chat_modes: Tuple[str, ...]
    execution_fn: Callable[..., Dict[str, Any]] = field(repr=False)

    def to_openrouter_Format(self) -> Dict[str, Any]:
        """Return OpenRouter / OpenAI function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


def _check_argument_type(value: Any, expected_type: Union[Type, Tuple[Type, ...]]) -> bool:
    """Strict type check that rejects `bool` when `int` or `float` is expected."""
    if expected_type is int or (isinstance(expected_type, tuple) and int in expected_type and bool not in expected_type):
        if isinstance(value, bool):
            return False
    if expected_type is float or (isinstance(expected_type, tuple) and float in expected_type and bool not in expected_type):
        if isinstance(value, bool):
            return False
    return isinstance(value, expected_type)


class ToolRegistry:
    """
    Central allowlisted registry of approved MySQL patient tools and ChromaDB
    knowledge tools.
    """

    def __init__(self, register_defaults: bool = True) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        if register_defaults:
            self._register_default_tools()

    def register_tool(self, tool_def: ToolDefinition) -> None:
        """Validate and register an approved `ToolDefinition`."""
        if not isinstance(tool_def, ToolDefinition):
            raise TypeError("tool_def must be an instance of ToolDefinition.")
        if not tool_def.name or not re.match(r"^[a-z][a-z0-9_]{2,63}$", tool_def.name):
            raise ValueError(f"Invalid tool name: '{tool_def.name}'.")
        if not tool_def.description or not isinstance(tool_def.description, str):
            raise ValueError(f"Tool '{tool_def.name}' must have a non-empty description.")
        if not isinstance(tool_def.input_schema, dict) or tool_def.input_schema.get("type") != "object":
            raise ValueError(f"Tool '{tool_def.name}' must define a JSON Schema object input_schema.")
        if not callable(tool_def.execution_fn):
            raise ValueError(f"Tool '{tool_def.name}' execution_fn must be callable.")
        if not tool_def.allowed_chat_modes or any(m not in ("patient", "general") for m in tool_def.allowed_chat_modes):
            raise ValueError(f"Tool '{tool_def.name}' has invalid allowed_chat_modes: {tool_def.allowed_chat_modes}.")

        # Enforce structural rule: mysql_patient tools can NEVER allow "general" chat mode
        source_type = tool_def.authorization_requirements.get("source_type")
        if source_type == "mysql_patient" and "general" in tool_def.allowed_chat_modes:
            raise ValueError(
                f"Security violation: MySQL patient tool '{tool_def.name}' cannot be enabled for General Chat."
            )

        self._tools[tool_def.name] = tool_def

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        if not isinstance(name, str):
            return None
        return self._tools.get(name.strip())

    def list_all_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def list_tools_for_mode(
        self,
        chat_mode: str,
        user_role: Optional[str] = None,
    ) -> List[ToolDefinition]:
        """
        Return only the tools permitted for `chat_mode` and `user_role`.
        In `general` mode, MySQL patient tools are strictly excluded.
        """
        mode_norm = str(chat_mode or "").strip().lower()
        if mode_norm not in ("patient", "general"):
            return []

        role_norm = str(user_role or "").strip().lower() if user_role else None
        available: List[ToolDefinition] = []

        for tool in self._tools.values():
            if mode_norm not in tool.allowed_chat_modes:
                continue
            # Double-lock: never expose mysql_patient tools in general mode
            if mode_norm == "general" and tool.authorization_requirements.get("source_type") == "mysql_patient":
                continue
            if role_norm:
                allowed_roles = tool.authorization_requirements.get("allowed_roles", ALL_CLINICAL_ROLES)
                if role_norm not in allowed_roles:
                    continue
            available.append(tool)

        return available

    def get_openrouter_tools_schema(
        self,
        chat_mode: str,
        user_role: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return the list of OpenRouter-compatible function definitions for the
        validated `chat_mode` and `user_role`.
        """
        tools = self.list_tools_for_mode(chat_mode=chat_mode, user_role=user_role)
        return [t.to_openrouter_Format() for t in tools]

    def validate_tool_call(
        self,
        tool_name: Any,
        arguments: Any,
        chat_mode: str,
        user_id: Any = None,
        user_role: Optional[str] = None,
        active_patient_id: Any = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate a requested tool call against the allowlist, chat-mode
        restrictions, role authorization, and argument schema.

        Returns:
            (is_valid: bool, error_message: str, validated_arguments: dict)
        """
        if not isinstance(tool_name, str) or not tool_name.strip():
            return False, "Tool name must be a non-empty string.", {}

        clean_name = tool_name.strip()
        tool_def = self.get_tool(clean_name)
        if tool_def is None:
            return False, f"Unknown or unapproved tool '{clean_name}'.", {}

        mode_norm = str(chat_mode or "").strip().lower()
        if mode_norm not in ("patient", "general"):
            return False, f"Invalid chat_mode '{chat_mode}'.", {}

        # 1. Enforce chat-mode allowlist
        if mode_norm not in tool_def.allowed_chat_modes or (
            mode_norm == "general"
            and tool_def.authorization_requirements.get("source_type") == "mysql_patient"
        ):
            return (
                False,
                f"Tool '{clean_name}' is not permitted in '{mode_norm}' chat mode.",
                {},
            )

        # 2. Enforce authentication & role requirements
        auth_reqs = tool_def.authorization_requirements
        if auth_reqs.get("requires_auth", True):
            if user_id is None or str(user_id).strip() == "":
                return False, f"Authentication required to invoke '{clean_name}'.", {}
            role_norm = str(user_role or "").strip().lower()
            allowed_roles = auth_reqs.get("allowed_roles", ALL_CLINICAL_ROLES)
            if role_norm not in allowed_roles:
                return (
                    False,
                    f"User role '{user_role}' is not authorized to invoke tool '{clean_name}'.",
                    {},
                )

        # 3. Validate arguments dictionary
        if arguments is None:
            args_dict: Dict[str, Any] = {}
        elif isinstance(arguments, dict):
            args_dict = dict(arguments)
        else:
            return False, f"Arguments for tool '{clean_name}' must be a JSON object/dict.", {}

        schema_props = tool_def.input_schema.get("properties", {})

        # Reject unexpected arguments not declared in input_schema
        unexpected_keys = [k for k in args_dict.keys() if k not in schema_props]
        if unexpected_keys:
            return (
                False,
                f"Unexpected argument(s) for tool '{clean_name}': {', '.join(unexpected_keys)}.",
                {},
            )

        # Auto-bind server-validated active_patient_id for patient tools if omitted by model,
        # and reject any attempt by the model to query a DIFFERENT patient_id than active_patient_id!
        if auth_reqs.get("requires_patient_auth", False):
            if active_patient_id is not None:
                try:
                    server_pid = int(active_patient_id)
                except (ValueError, TypeError):
                    return False, f"Invalid server active_patient_id '{active_patient_id}'.", {}

                if "patient_id" not in args_dict or args_dict["patient_id"] is None:
                    args_dict["patient_id"] = server_pid
                else:
                    try:
                        requested_pid = int(args_dict["patient_id"]) if not isinstance(args_dict["patient_id"], bool) else -1
                    except (ValueError, TypeError):
                        return False, f"Invalid patient_id argument '{args_dict['patient_id']}'.", {}
                    if requested_pid != server_pid:
                        return (
                            False,
                            f"Cross-patient access rejected: tool requested patient_id={requested_pid} "
                            f"but active authorized patient_id is {server_pid}.",
                            {},
                        )
                    args_dict["patient_id"] = server_pid

        # Check required arguments
        for req_arg in tool_def.required_arguments:
            if req_arg not in args_dict or args_dict[req_arg] is None:
                return (
                    False,
                    f"Missing required argument '{req_arg}' for tool '{clean_name}'.",
                    {},
                )

        # Validate each argument's type and safety constraints
        validated_args: Dict[str, Any] = {}
        for arg_name, arg_val in args_dict.items():
            expected_type = tool_def.argument_types.get(arg_name)
            if expected_type is not None and not _check_argument_type(arg_val, expected_type):
                return (
                    False,
                    f"Invalid type for argument '{arg_name}' in tool '{clean_name}': "
                    f"expected {expected_type}, got {type(arg_val).__name__}.",
                    {},
                )

            if arg_name == "patient_id":
                if isinstance(arg_val, bool) or not isinstance(arg_val, int) or arg_val <= 0:
                    return (
                        False,
                        f"Invalid patient_id '{arg_val}': must be a positive integer.",
                        {},
                    )

            if isinstance(arg_val, str):
                cleaned_str = arg_val.strip()
                if not cleaned_str and arg_name in tool_def.required_arguments:
                    return (
                        False,
                        f"Argument '{arg_name}' in tool '{clean_name}' cannot be empty.",
                        {},
                    )
                if _UNSAFE_ARG_PATTERN.search(cleaned_str):
                    return (
                        False,
                        f"Unsafe SQL or code pattern rejected in argument '{arg_name}'.",
                        {},
                    )
                validated_args[arg_name] = cleaned_str
            else:
                validated_args[arg_name] = arg_val

        return True, "", validated_args

    # -------------------------------------------------------------------------
    # Default Jeevan Setu Tool Registration
    # -------------------------------------------------------------------------
    def _register_default_tools(self) -> None:
        # --- A. MYSQL PATIENT TOOLS (Patient Chat Only) ---
        self.register_tool(
            ToolDefinition(
                name="get_patient_summary",
                description=(
                    "Retrieve verified MySQL demographic, admission, ward/bed assignment, "
                    "attending doctor, and primary diagnosis summary for the active authorized patient."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        }
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={"patient_id": int},
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_summary,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_patient_vitals",
                description=(
                    "Retrieve latest vital signs telemetry (heart rate, systolic/diastolic blood pressure, "
                    "respiratory rate, temperature, SpO2, consciousness) with units, timestamps, "
                    "historical readings, longitudinal trends, and stale-observation warnings."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        },
                        "include_history": {
                            "type": "boolean",
                            "description": "Whether to include recent historical vital readings.",
                        },
                        "history_limit": {
                            "type": "integer",
                            "description": "Maximum number of historical vital readings to return (1-20).",
                        },
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={
                    "patient_id": int,
                    "include_history": bool,
                    "history_limit": int,
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_vitals,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_patient_ews",
                description=(
                    "Retrieve the authoritative persisted Early Warning Score (EWS), clinical risk "
                    "level, parameter score breakdown, Composite Stability Index (CSI), and calculation timestamp."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        },
                        "include_history": {
                            "type": "boolean",
                            "description": "Whether to include historical EWS scores.",
                        },
                        "history_limit": {
                            "type": "integer",
                            "description": "Maximum number of historical EWS entries (1-20).",
                        },
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={
                    "patient_id": int,
                    "include_history": bool,
                    "history_limit": int,
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_ews,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_patient_recommendations",
                description=(
                    "Retrieve the authoritative persisted ICU/HDU transfer recommendation, target ward, "
                    "clinical rationale, clinician decision history, and XAI feature explanations."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        },
                        "include_explanations": {
                            "type": "boolean",
                            "description": "Whether to include Explainable AI (XAI) feature contributions.",
                        },
                        "include_decision_history": {
                            "type": "boolean",
                            "description": "Whether to include past clinician transfer decisions.",
                        },
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={
                    "patient_id": int,
                    "include_explanations": bool,
                    "include_decision_history": bool,
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_recommendations,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_patient_transfer_history",
                description=(
                    "Retrieve persisted ICU/HDU ward and bed transfer records and clinician decision logs "
                    "for the authorized patient."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of transfer records to return (1-20).",
                        },
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={"patient_id": int, "limit": int},
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_transfer_history,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_patient_clinical_notes",
                description=(
                    "Retrieve documented primary diagnosis and clinical progress notes / medical history "
                    "for the authorized patient (restricted to clinical staff roles)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of clinical notes to return (1-20).",
                        },
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={"patient_id": int, "limit": int},
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": STAFF_ONLY_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_clinical_notes,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_patient_alerts",
                description=(
                    "Retrieve active and recent clinical telemetry alerts (e.g., abnormal vitals, high EWS, "
                    "pending transfer alerts) for the authorized patient."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of alerts to return (1-20).",
                        },
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={"patient_id": int, "limit": int},
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_alerts,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_patient_bed_and_ward_details",
                description=(
                    "Retrieve current ward name, ward type (ICU/HDU/General), bed number, bed status, "
                    "floor number, and allocation timestamp for the authorized patient."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "patient_id": {
                            "type": "integer",
                            "description": "Authorized numeric patient ID.",
                        }
                    },
                    "required": ["patient_id"],
                    "additionalProperties": False,
                },
                required_arguments=("patient_id",),
                argument_types={"patient_id": int},
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient",),
                execution_fn=get_patient_bed_and_ward_details,
            )
        )

        # --- B. CHROMADB KNOWLEDGE TOOLS (Patient Chat & General Chat) ---
        self.register_tool(
            ToolDefinition(
                name="search_knowledge_base",
                description=(
                    "Search the shared Jeevan Setu ChromaDB clinical knowledge base for medical "
                    "reference information, clinical concepts, protocols, or guidelines."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Semantic search query for the clinical knowledge base.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of relevant chunks to retrieve (1-20).",
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional knowledge category filter.",
                        },
                        "min_relevance": {
                            "type": "number",
                            "description": "Minimum relevance score threshold in [0.0, 1.0].",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                required_arguments=("query",),
                argument_types={
                    "query": str,
                    "top_k": int,
                    "category": str,
                    "min_relevance": (int, float),
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": False,
                    "source_type": "chroma_knowledge",
                },
                allowed_chat_modes=("patient", "general"),
                execution_fn=search_knowledge_base,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="search_clinical_protocols",
                description=(
                    "Search approved clinical protocols (such as Early Warning Score (EWS) thresholds, "
                    "vital sign escalation rules, and acute care protocols) in ChromaDB."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Clinical protocol search query.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of chunks to return (1-20).",
                        },
                        "min_relevance": {
                            "type": "number",
                            "description": "Minimum relevance score threshold in [0.0, 1.0].",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                required_arguments=("query",),
                argument_types={
                    "query": str,
                    "top_k": int,
                    "min_relevance": (int, float),
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": False,
                    "source_type": "chroma_knowledge",
                },
                allowed_chat_modes=("patient", "general"),
                execution_fn=search_clinical_protocols,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="search_hospital_sops",
                description=(
                    "Search hospital Standard Operating Procedures (SOPs) for ICU/HDU handoff, "
                    "bed management workflows, and staff escalation procedures."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Hospital SOP search query.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of chunks to return (1-20).",
                        },
                        "min_relevance": {
                            "type": "number",
                            "description": "Minimum relevance score threshold in [0.0, 1.0].",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                required_arguments=("query",),
                argument_types={
                    "query": str,
                    "top_k": int,
                    "min_relevance": (int, float),
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": False,
                    "source_type": "chroma_knowledge",
                },
                allowed_chat_modes=("patient", "general"),
                execution_fn=search_hospital_sops,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="search_approved_guidelines",
                description=(
                    "Search approved ICU <-> HDU step-down and step-up transfer eligibility guidelines "
                    "and clinical stability criteria in ChromaDB."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Clinical or transfer guideline search query.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of chunks to return (1-20).",
                        },
                        "min_relevance": {
                            "type": "number",
                            "description": "Minimum relevance score threshold in [0.0, 1.0].",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                required_arguments=("query",),
                argument_types={
                    "query": str,
                    "top_k": int,
                    "min_relevance": (int, float),
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": False,
                    "source_type": "chroma_knowledge",
                },
                allowed_chat_modes=("patient", "general"),
                execution_fn=search_approved_guidelines,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_document_source",
                description=(
                    "Retrieve chunks and source provenance (document_id, source path, page numbers, "
                    "version) for a specific knowledge-base document ID."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "Stable knowledge document identifier (e.g., DOC_...).",
                        },
                        "document_version": {
                            "type": "string",
                            "description": "Optional document version filter.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of document chunks to retrieve (1-20).",
                        },
                    },
                    "required": ["document_id"],
                    "additionalProperties": False,
                },
                required_arguments=("document_id",),
                argument_types={
                    "document_id": str,
                    "document_version": str,
                    "top_k": int,
                },
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": False,
                    "source_type": "chroma_knowledge",
                },
                allowed_chat_modes=("patient", "general"),
                execution_fn=get_document_source,
            )
        )


_DEFAULT_REGISTRY: Optional[ToolRegistry] = None


def get_default_tool_registry() -> ToolRegistry:
    """Return the singleton allowlisted `ToolRegistry`."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ToolRegistry(register_defaults=True)
    return _DEFAULT_REGISTRY


__all__ = [
    "ALL_CLINICAL_ROLES",
    "STAFF_ONLY_ROLES",
    "ToolDefinition",
    "ToolRegistry",
    "get_default_tool_registry",
]

