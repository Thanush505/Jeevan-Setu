"""
tests/test_tool_registry.py

Pytest suite for Jeevan Setu Tool Registry (`chatbot/tools/tool_registry.py`).

Tests:
1. Valid tool registration and schema completeness.
2. Unknown tool rejection.
3. Invalid arguments (unexpected keys, missing required args, wrong types, bool-as-int).
4. Unauthorized user role rejection.
5. General Chat tool list strictly excludes all MySQL patient tools.
6. Cross-patient argument override rejection.
7. SQL / code injection payload rejection in string arguments.
8. Prevention of registering a MySQL patient tool with 'general' chat mode.
"""

import pytest

from chatbot.tools.tool_registry import (
    ALL_CLINICAL_ROLES,
    STAFF_ONLY_ROLES,
    ToolDefinition,
    ToolRegistry,
    get_default_tool_registry,
)


def test_01_valid_default_tool_registration():
    registry = get_default_tool_registry()
    all_tools = registry.list_all_tools()
    tool_names = {t.name for t in all_tools}

    expected_mysql_tools = {
        "get_patient_summary",
        "get_patient_vitals",
        "get_patient_ews",
        "get_patient_recommendations",
        "get_patient_transfer_history",
        "get_patient_clinical_notes",
        "get_patient_alerts",
        "get_patient_bed_and_ward_details",
    }
    expected_chroma_tools = {
        "search_knowledge_base",
        "search_clinical_protocols",
        "search_hospital_sops",
        "search_approved_guidelines",
        "get_document_source",
    }

    assert expected_mysql_tools.issubset(tool_names)
    assert expected_chroma_tools.issubset(tool_names)

    for tool in all_tools:
        assert tool.description
        assert tool.input_schema.get("type") == "object"
        assert callable(tool.execution_fn)
        or_schema = tool.to_openrouter_Format()
        assert or_schema["type"] == "function"
        assert or_schema["function"]["name"] == tool.name


def test_02_unknown_tool_rejection():
    registry = ToolRegistry()
    ok, err, args = registry.validate_tool_call(
        tool_name="execute_arbitrary_sql_query",
        arguments={"query": "SELECT * FROM patients"},
        chat_mode="patient",
        user_id=1,
        user_role="doctor",
        active_patient_id=101,
    )
    assert ok is False
    assert "Unknown or unapproved tool" in err
    assert args == {}


def test_03_invalid_arguments_rejected():
    registry = ToolRegistry()

    # Unexpected argument
    ok, err, _ = registry.validate_tool_call(
        tool_name="get_patient_summary",
        arguments={"patient_id": 101, "raw_sql": "DROP TABLE patients"},
        chat_mode="patient",
        user_id=1,
        user_role="doctor",
        active_patient_id=101,
    )
    assert ok is False
    assert "Unexpected argument" in err

    # Wrong type (string instead of int)
    ok, err, _ = registry.validate_tool_call(
        tool_name="get_patient_vitals",
        arguments={"patient_id": 101, "history_limit": "five"},
        chat_mode="patient",
        user_id=1,
        user_role="doctor",
        active_patient_id=101,
    )
    assert ok is False
    assert "Invalid type" in err

    # Boolean passed where int is expected
    ok, err, _ = registry.validate_tool_call(
        tool_name="get_patient_vitals",
        arguments={"patient_id": 101, "history_limit": True},
        chat_mode="patient",
        user_id=1,
        user_role="doctor",
        active_patient_id=101,
    )
    assert ok is False
    assert "Invalid type" in err

    # Missing required query argument for ChromaDB tool
    ok, err, _ = registry.validate_tool_call(
        tool_name="search_knowledge_base",
        arguments={},
        chat_mode="general",
        user_id=1,
        user_role="doctor",
    )
    assert ok is False
    assert "Missing required argument 'query'" in err


def test_04_unauthorized_user_role_rejection():
    registry = ToolRegistry()

    # Unknown role
    ok, err, _ = registry.validate_tool_call(
        tool_name="get_patient_summary",
        arguments={"patient_id": 101},
        chat_mode="patient",
        user_id=1,
        user_role="anonymous_guest",
        active_patient_id=101,
    )
    assert ok is False
    assert "not authorized" in err

    # Attendant attempting to call staff-only clinical notes tool
    ok, err, _ = registry.validate_tool_call(
        tool_name="get_patient_clinical_notes",
        arguments={"patient_id": 101},
        chat_mode="patient",
        user_id=50,
        user_role="attendant",
        active_patient_id=101,
    )
    assert ok is False
    assert "not authorized" in err


def test_05_general_chat_excludes_and_rejects_mysql_tools():
    registry = ToolRegistry()
    general_tools = registry.list_tools_for_mode("general", user_role="doctor")
    general_names = {t.name for t in general_tools}

    assert "get_patient_summary" not in general_names
    assert "get_patient_vitals" not in general_names
    assert "get_patient_ews" not in general_names
    assert "search_knowledge_base" in general_names
    assert "search_clinical_protocols" in general_names

    # Validation must also reject calling a MySQL tool in general mode
    ok, err, _ = registry.validate_tool_call(
        tool_name="get_patient_vitals",
        arguments={"patient_id": 101},
        chat_mode="general",
        user_id=1,
        user_role="doctor",
    )
    assert ok is False
    assert "not permitted in 'general' chat mode" in err


def test_06_cross_patient_id_override_rejected():
    registry = ToolRegistry()
    # Active patient on server is 101, but tool call requests patient 999
    ok, err, _ = registry.validate_tool_call(
        tool_name="get_patient_ews",
        arguments={"patient_id": 999},
        chat_mode="patient",
        user_id=1,
        user_role="doctor",
        active_patient_id=101,
    )
    assert ok is False
    assert "Cross-patient access rejected" in err


def test_07_no_arbitrary_sql_or_code_in_arguments():
    registry = ToolRegistry()
    ok, err, _ = registry.validate_tool_call(
        tool_name="search_knowledge_base",
        arguments={"query": "normal spo2; DROP TABLE patients;"},
        chat_mode="general",
        user_id=1,
        user_role="doctor",
    )
    assert ok is False
    assert "Unsafe SQL or code pattern rejected" in err


def test_08_cannot_register_mysql_tool_in_general_mode():
    registry = ToolRegistry(register_defaults=False)
    with pytest.raises(ValueError, match="Security violation"):
        registry.register_tool(
            ToolDefinition(
                name="unsafe_patient_tool",
                description="Should not be allowed in general mode",
                input_schema={"type": "object", "properties": {}},
                required_arguments=(),
                argument_types={},
                authorization_requirements={
                    "requires_auth": True,
                    "allowed_roles": ALL_CLINICAL_ROLES,
                    "requires_patient_auth": True,
                    "source_type": "mysql_patient",
                },
                allowed_chat_modes=("patient", "general"),
                execution_fn=lambda **kw: {},
            )
        )

