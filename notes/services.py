from django.core.files.base import ContentFile
from django.utils import timezone
from files.models import FileCategory, ProjectFile

"""
This module contains service layer helpers for the Notes application.
Directs background synchronization of notes text content to physical Markdown (.md) documents
inside the Files / Document Management directories tree.
"""


class KBService:
    """
    Service layer providing file synchronization pipelines for KnowledgeBaseNote instances.
    """
    @staticmethod
    def save_note_as_file(note, user, old_title=None):
        """
        Saves a KnowledgeBaseNote as a .md file in the project's "Notes" folder.
        Always reuses the SAME root-level "Notes" folder – never duplicates it.
        If the note's title has changed, renames the existing file reference to avoid orphans.
        Also synchronizes soft-deletion (trash/restore) states to the corresponding ProjectFile.
        """
        if not note.project:
            return

        # Find existing Notes folder first; only create if none exists.
        creator = user or note.author
        if not creator:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            creator = (
                User.objects.filter(is_superuser=True, is_active=True).first()
                or User.objects.filter(is_active=True).first()
            )

        notes_cat = (
            FileCategory.objects
            .filter(name="Notes", project=note.project, parent__isnull=True)
            .first()
        )
        if not notes_cat:
            notes_cat = FileCategory.objects.create(
                name="Notes",
                project=note.project,
                parent=None,
                created_by=creator,
            )

        file_name = f"{note.title}.md".replace("/", "-")
        content_bytes = note.content.encode("utf-8")

        # 1. Handle title change (renaming old file)
        if old_title and old_title != note.title:
            old_file_name = f"{old_title}.md".replace("/", "-")
            old_file = (
                ProjectFile.objects.filter(
                    original_name=old_file_name, project=note.project, category=notes_cat
                )
                .order_by("-version")
                .first()
            )
            if old_file:
                # Delete the old file physical reference to avoid name clash on storage,
                # then update reference properties and write new file content.
                if old_file.file:
                    old_file.file.delete(save=False)
                old_file.original_name = file_name
                old_file.description = f"Auto-generated from KB Note: {note.title}"
                
                # Sync trash state if needed
                if note.is_in_trash:
                    old_file.is_in_trash = True
                    old_file.deleted_at = note.deleted_at or timezone.now()
                    old_file.deleted_by = note.deleted_by or creator
                else:
                    old_file.is_in_trash = False
                    old_file.deleted_at = None
                    old_file.deleted_by = None
                    
                old_file.file.save(file_name, ContentFile(content_bytes), save=False)
                old_file.save()
                return

        # 2. Find if a file with the new name already exists (either in trash or active)
        existing_file = (
            ProjectFile.objects.filter(
                original_name=file_name, project=note.project, category=notes_cat
            )
            .order_by("-version")
            .first()
        )

        if existing_file:
            # Sync trash state
            if note.is_in_trash:
                existing_file.is_in_trash = True
                existing_file.deleted_at = note.deleted_at or timezone.now()
                existing_file.deleted_by = note.deleted_by or creator
                existing_file.save()
            else:
                existing_file.is_in_trash = False
                existing_file.deleted_at = None
                existing_file.deleted_by = None
                if existing_file.file:
                    existing_file.file.delete(save=False)
                existing_file.file.save(file_name, ContentFile(content_bytes), save=False)
                existing_file.save()
        else:
            # If the note is already in trash upon creation, create the ProjectFile in trash
            pf = ProjectFile(
                original_name=file_name,
                project=note.project,
                category=notes_cat,
                uploaded_by=creator,
                description=f"Auto-generated from KB Note: {note.title}",
                is_in_trash=note.is_in_trash,
                deleted_at=note.deleted_at if note.is_in_trash else None,
                deleted_by=note.deleted_by if note.is_in_trash else None,
            )
            pf.file.save(file_name, ContentFile(content_bytes), save=False)
            pf.save()
