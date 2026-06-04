from django.conf import settings
from .models import Message

def summarize_chat(room_id, limit=50):
    """
    Summarizes the last 'limit' messages in a chat room. (Google AI Gemini Disabled)
    """
    return "AI Summary is unavailable: Google AI integration has been disabled."

def extract_tasks_from_chat(room_id, limit=20):
    """
    Identifies potential tasks from recent chat messages. (Google AI Gemini Disabled)
    """
    return []
