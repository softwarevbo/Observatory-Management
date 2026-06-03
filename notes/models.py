from django.conf import settings
from django.db import models


class KnowledgeBaseNote(models.Model):
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

    # Trash fields
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
        super().save(*args, **kwargs)
        if self.project:
            from django.core.files.base import ContentFile
            from files.models import FileCategory, ProjectFile

            notes_cat, _ = FileCategory.objects.get_or_create(
                name="Notes", project=self.project, defaults={"created_by": self.author}
            )

            file_name = f"{self.title}.md".replace("/", "-")
            content_bytes = self.content.encode("utf-8")

            existing_file = (
                ProjectFile.objects.filter(
                    original_name=file_name, project=self.project, category=notes_cat
                )
                .order_by("-version")
                .first()
            )

            if existing_file:
                if existing_file.file:
                    existing_file.file.delete(save=False)
                existing_file.file.save(
                    file_name, ContentFile(content_bytes), save=False
                )
                existing_file.save()
            else:
                pf = ProjectFile(
                    original_name=file_name,
                    project=self.project,
                    category=notes_cat,
                    uploaded_by=self.author,
                    description=f"Auto-generated from KB Note: {self.title}",
                )
                pf.file.save(file_name, ContentFile(content_bytes), save=False)
                pf.save()
