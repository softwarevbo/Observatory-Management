from django.core.files.base import ContentFile
from files.models import FileCategory, ProjectFile


class KBService:
    @staticmethod
    def save_note_as_file(note, user):
        """
        Saves a KnowledgeBaseNote as a .md file in the project's "Notes" folder.
        Always reuses the SAME Notes category – never creates a new one.
        """
        if not note.project:
            return

        # Find existing Notes folder first; only create if none exists.
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
                created_by=user,
            )

        file_name = f"{note.title}.md".replace("/", "-")
        content_bytes = note.content.encode("utf-8")

        existing_file = (
            ProjectFile.objects.filter(
                original_name=file_name, project=note.project, category=notes_cat
            )
            .order_by("-version")
            .first()
        )

        if existing_file:
            if existing_file.file:
                existing_file.file.delete(save=False)
            existing_file.file.save(file_name, ContentFile(content_bytes), save=False)
            existing_file.save()
        else:
            pf = ProjectFile(
                original_name=file_name,
                project=note.project,
                category=notes_cat,
                uploaded_by=user,
                description=f"Auto-generated from KB Note: {note.title}",
            )
            pf.file.save(file_name, ContentFile(content_bytes), save=False)
            pf.save()
