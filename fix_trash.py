import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from files.models import FileCategory, ProjectFile
from django.utils import timezone

def trash_descendants(cat):
    now = timezone.now()
    # Trash all files in this category
    ProjectFile.objects.filter(category=cat, is_in_trash=False).update(
        is_in_trash=True, deleted_at=now, deleted_by=cat.deleted_by
    )
    # Recursively trash children
    for child in cat.children.filter(is_in_trash=False):
        child.is_in_trash = True
        child.deleted_at = now
        child.deleted_by = cat.deleted_by
        child.save()
        trash_descendants(child)

# Find already trashed categories and recursively trash their descendants
trashed_cats = FileCategory.objects.filter(is_in_trash=True)
for cat in trashed_cats:
    trash_descendants(cat)

print("Fixed trashed descendants")
