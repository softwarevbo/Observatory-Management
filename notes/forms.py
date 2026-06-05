from django import forms
from .models import KnowledgeBaseNote

"""
This module defines form components for creating and editing Knowledge Base notes.
"""

class KnowledgeBaseNoteForm(forms.ModelForm):
    """
    Form model binding to KnowledgeBaseNote.
    Sets standard HTML attributes and placeholder cues.
    """
    class Meta:
        model = KnowledgeBaseNote
        fields = ["title", "content"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Note title"}
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 15,
                    "placeholder": "# Heading\n\nWrite your note in Markdown...",
                }
            ),
        }
