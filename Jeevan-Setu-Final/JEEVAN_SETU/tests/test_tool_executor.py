"""
tests/test_tool_executor.py

Pytest suite for Jeevan Setu Tool Executor (`chatbot/tools/tool_executor.py`).

Tests:
1. OpenRouter native `tool_calls` parsing (`parse_openrouter_tool_calls`).
2. Unsupported / malformed tool-call handling.
3. Structured-output JSON fallback validation (`parse_structured_tool_call_fallback`).
4. Safe execution of authorized MySQL patient tools and ChromaDB knowledge tools.
5. Executor-level blocking of MySQL tools in General Chat even when `patient_id` is passed.
6. Safe handling of tool execution errors without leaking stack traces or SQL.
"""

from unittest.mock import MagicMock

from chatbot.tools.tool_executor import (
    execute_tool_call,
    parse_openrouter_tool_calls,
    parse_structured_tool_call_fallback,
)
from chatbot.tools.tool_registry import ToolDefinition, ToolRegistry, ALL_CLINICAL_ROLES


def test_01_openrouter_native_tool_call_parsing():
    openrouter_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_abc_1",
                            "type": "function",
                            "function": {
                                "name": "get_patient_vitals",
                                "arguments": '{"patient_id": 501, "include_history": true}',
                            },
                        },
                        {
                            "id": "call_abc_2",
                            "type": "function",
                            "function": {
                                "name": "search_clinical_protocols",
                                "arguments": '{"query": "EWS escalation threshold", "top_k": 3}',
                            },
                        },
                    ],
                }
            }
        ]
    }

    calls, errs = parse_openrouter_tool_calls(openrouter_response)
    assert errs == []
    assert len(calls) == 2
    assert calls[0]["id"] == "call_abc_1"
    assert calls[0]["name"] == "get_patient_vitals"
    assert calls[0]["arguments"] == {"patient_id": 501, "include_history": True}
    assert calls[1]["name"] == "search_clinical_protocols"
    assert calls[1]["arguments"]["top_k"] == 3


def test_02_unsupported_and_malformed_tool_call_handling():
    malformed_response = {
        "message": {
            "tool_calls": [
                {"id": "bad_1", "function": {"name": "", "arguments": "{}"}},
                {"id": "bad_2", "function": {"name": "get_patient_ews", "arguments": "{invalid_json"}},
                {"id": "bad_3", "function": {"name": "get_patient_ews", "arguments": "[1, 2, 3]"}},
            ]
        }
    }

    calls, errs = parse_openrouter_tool_calls(malformed_response)
    assert calls == []
    assert len(errs) == 3


def test_03_structured_output_fallback_validation():
    # Valid structured JSON tool call inside fenced block
    fenced_content = """```json
    {
      "tool_calls": [
        {"name": "search_approved_guidelines", "arguments": {"query": "ICU to HDU transfer", "top_k": 2}}
      ]
    }
    ```"""
    calls, errs = parse_structured_tool_call_fallback(fenced_content)
    assert errs == []
    assert len(calls) == 1
    assert calls[0]["name"] == "search_approved_guidelines"
    assert calls[0]["arguments"] == {"query": "ICU to HDU transfer", "top_k": 2}

    # Unknown / unapproved tool inside fallback JSON is rejected
    unapproved_content = '{"tool": "execute_raw_sql", "arguments": {"sql": "SELECT * FROM users"}}'
    calls2, errs2 = parse_structured_tool_call_fallback(unapproved_content)
    assert calls2 == []
    assert any("unknown/unapproved tool" in e for e in errs2)


def test_04_general_chat_blocks_mysql_tool_even_with_patient_id():
    provider_spy = MagicMock()
    req_ctx = {
        "user_id": 10,
        "user_role": "doctor",
        "chat_mode": "general",
        "patient_id": 501,
        "patient_data_provider": provider_spy,
    }

    res = execute_tool_call(
        tool_name="get_patient_vitals",
        arguments={"patient_id": 501},
        request_context=req_ctx,
    )
    assert res["success"] is False
    assert res["status"] == "unauthorized_mode"
    assert "prohibited in General Chat mode" in res["error"]
    provider_spy.assert_not_called()


def test_05_tool_execution_error_handled_without_leaking_internals():
    registry = ToolRegistry(register_defaults=False)

    def crashing_tool(query: str, **kwargs):
        raise RuntimeError("FATAL DB CREDENTIAL LEAK mysql://root:secret_password@localhost/jeevan_setu")

    registry.register_tool(
        ToolDefinition(
            name="search_knowledge_base",
            description="Test tool that raises an unexpected error",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            required_arguments=("query",),
            argument_types={"query": str},
            authorization_requirements={
                "requires_auth": True,
                "allowed_roles": ALL_CLINICAL_ROLES,
                "requires_patient_auth": False,
                "source_type": "chroma_knowledge",
            },
            allowed_chat_modes=("patient", "general"),
            execution_fn=crashing_tool,
        )
    )

    res = execute_tool_call(
        tool_name="search_knowledge_base",
        arguments={"query": "sepsis"},
        request_context={"user_id": 1, "user_role": "doctor", "chat_mode": "general"},
        registry=registry,
    )
    assert res["success"] is False
    assert res["status"] == "execution_error"
    assert "secret_password" not in res["error"]
    assert "mysql://" not in res["error"]

