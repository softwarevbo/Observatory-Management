from django.conf import settings
from .models import Message

"""
This module contains helpers for AI integration features within the chat system.
Note: Google AI Gemini has been disabled, so these features return stub results.
"""

def summarize_chat(room_id, limit=50):
    """
    Summarizes the last 'limit' messages in a chat room.
    Currently disabled due to Google AI integration being deactivated.
    """
    return "AI Summary is unavailable: Google AI integration has been disabled."

def extract_tasks_from_chat(room_id, limit=20):
    """
    Identifies potential tasks from recent chat messages using AI NLP parser.
    Currently disabled due to Google AI integration being deactivated.
    """
    return []
