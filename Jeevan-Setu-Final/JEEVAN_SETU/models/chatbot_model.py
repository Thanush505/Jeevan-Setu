"""
models/chatbot_model.py — Model for chatbot conversation history.
"""

from database.db import db


class ChatbotConversation:
    """Model for storing chatbot interactions."""

    @staticmethod
    def save(user_id, user_message, bot_response, patient_id=None,
             intent=None, confidence=None):
        """Save a chatbot conversation turn."""
        bot_resp = bot_response if bot_response is not None else ""
        return db.execute_query(
            """INSERT INTO chatbot_conversations
               (user_id, patient_id, user_message, bot_response, intent, confidence)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, patient_id, user_message, bot_resp, intent, confidence)
        )

    @staticmethod
    def get_history(user_id, limit=20):
        """Get conversation history for a user."""
        return db.execute_query(
            """SELECT * FROM chatbot_conversations WHERE user_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit), fetch=True
        )

    @staticmethod
    def get_by_patient(patient_id, limit=20):
        """Get conversations related to a specific patient."""
        return db.execute_query(
            """SELECT * FROM chatbot_conversations WHERE patient_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (patient_id, limit), fetch=True
        )
