import google.generativeai as genai
from django.conf import settings
from .models import Message

def summarize_chat(room_id, limit=50):
    """
    Summarizes the last 'limit' messages in a chat room using Gemini.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return "AI Summary is unavailable: GEMINI_API_KEY not configured."

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')

    messages = Message.objects.filter(room__room_id=room_id).order_by('-created_at')[:limit]
    if not messages:
        return "No messages to summarize."

    # Reverse to get chronological order
    chat_history = "\n".join([f"{m.sender.username}: {m.content}" for m in reversed(messages)])

    prompt = f"""
    The following is a chat history from a project management tool. 
    Please provide a concise summary of the key points discussed and any action items identified.
    
    Chat History:
    {chat_history}
    
    Summary:
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def extract_tasks_from_chat(room_id, limit=20):
    """
    Identifies potential tasks from recent chat messages.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return []

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')

    messages = Message.objects.filter(room__room_id=room_id).order_by('-created_at')[:limit]
    chat_history = "\n".join([f"{m.sender.username}: {m.content}" for m in reversed(messages)])

    prompt = f"""
    Analyze the following chat history and extract potential tasks or action items.
    Return only a list of tasks, one per line, starting with '- '.
    
    Chat History:
    {chat_history}
    """

    try:
        response = model.generate_content(prompt)
        tasks = [line.strip('- ') for line in response.text.strip().split('\n') if line.strip()]
        return tasks
    except:
        return []
