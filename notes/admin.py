from django.contrib import admin
from .models import KnowledgeBaseNote


@admin.register(KnowledgeBaseNote)
class KnowledgeBaseNoteAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "author", "created_at"]
    list_filter = ["project", "is_in_trash"]
    search_fields = ["title", "content"]
