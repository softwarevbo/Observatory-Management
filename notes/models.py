from django.conf import settings
from django.db import models

"""
This module defines the database models for the Notes / Knowledge Base application.
It establishes schemas for notes, modules references, authors, soft deletion, and 
triggers automatic Markdown document synchronization on save or deletion.
"""


class KnowledgeBaseNote(models.Model):
    """
    Model representing notes or knowledge base guides attached to projects and modules.
    Tracks revision timestamps, author profiles, and soft deletion flags.
    """
    project = models.ForeignKey(
        "tasks.Project",
        on_delete=models.CASCADE,
        related_name="kb_notes",
        null=True,
        blank=True,
    )
    module = models.ForeignKey(
        "tasks.ProjectModule",
        on_delete=models.SET_NULL,
        related_name="kb_notes",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="Markdown format supported")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft deletion properties
    is_in_trash = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_notes",
    )

    class Meta:
        db_table = "tasks_knowledgebasenote"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Overrides save() to trigger automatic Markdown document synchronization.
        Checks if the note title was updated to rename the existing ProjectFile reference.
        """
        old_title = None
        if self.pk:
            try:
                old_instance = KnowledgeBaseNote.objects.get(pk=self.pk)
                old_title = old_instance.title
            except KnowledgeBaseNote.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if self.project:
            from .services import KBService
            KBService.save_note_as_file(self, self.author, old_title=old_title)

    def delete(self, *args, **kwargs):
        """
        Overrides delete() to ensure that the corresponding ProjectFile in the Notes folder,
        including its physical file on disk, is permanently cleaned up.
        """
        if self.project:
            from files.models import FileCategory, ProjectFile
            notes_cat = (
                FileCategory.objects
                .filter(name="Notes", project=self.project, parent__isnull=True)
                .first()
            )
            if notes_cat:
                file_name = f"{self.title}.md".replace("/", "-")
                associated_files = ProjectFile.objects.filter(
                    original_name=file_name, project=self.project, category=notes_cat
                )
                for pf in associated_files:
                    if pf.file:
                        pf.file.delete(save=False)
                    pf.delete()
        super().delete(*args, **kwargs)
