from django import forms
from .models import KnowledgeBaseNote


class KnowledgeBaseNoteForm(forms.ModelForm):
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
