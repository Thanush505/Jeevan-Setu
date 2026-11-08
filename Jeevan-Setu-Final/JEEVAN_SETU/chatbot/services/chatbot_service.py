"""
chatbot/services/chatbot_service.py — High-level Chatbot Service Façade for Jeevan Setu.

Delegates to the authoritative clinical reasoning engine (`chatbot_engine.py`)
and OpenRouter AI integration (`openrouter_service.py`).
"""

from chatbot.services.chatbot_engine import (
    process_message,
    process_conversational_message,
    get_patient_clinical_context,
    search_patients_for_chat,
    format_structured_patient_summary,
    format_vital_parameters_analysis,
    format_transfer_decision_explanation,
    format_decision_history_and_overrides,
    format_documented_diagnosis,
    verify_user_patient_access,
    get_authorized_patients_for_user,
)
from chatbot.services.openrouter_service import (
    query_openrouter_gemini,
    is_ai_configured,
    get_openrouter_model,
    get_openrouter_api_key,
    build_controlled_patient_context,
)


class ChatbotService:
    """Service layer wrapping Jeevan Setu conversational clinical assistant operations."""

    @staticmethod
    def handle_message(user_id, message, active_patient_id=None, user_role="doctor", mode="patient"):
        return process_conversational_message(
            user_id=user_id,
            message=message,
            active_patient_id=active_patient_id,
            user_role=user_role,
            mode=mode,
        )

    @staticmethod
    def handle_patient_query(user_id, patient_id, message, user_role="doctor"):
        return process_message(
            user_id=user_id,
            patient_id=patient_id,
            message=message,
            user_role=user_role,
        )

    @staticmethod
    def get_authorized_patients(user):
        return get_authorized_patients_for_user(user)

    @staticmethod
    def verify_patient_access(user, patient_id):
        return verify_user_patient_access(user, patient_id)

