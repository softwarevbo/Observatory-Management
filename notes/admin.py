from django.contrib import admin
from .models import KnowledgeBaseNote

"""
This module registers the Notes application models in the Django Admin portal.
"""

@admin.register(KnowledgeBaseNote)
class KnowledgeBaseNoteAdmin(admin.ModelAdmin):
    """
    Admin configuration for KnowledgeBaseNote model.
    Organizes search indices, list filters, and display fields.
    """
    list_display = ["title", "project", "author", "created_at"]
    list_filter = ["project", "is_in_trash"]
    search_fields = ["title", "content"]
