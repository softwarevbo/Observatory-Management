import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from files.models import FileCategory, ProjectFile
from tasks.models import Project


def cleanup_categories():
    # 1. Merge "releases" into "Releases"
    # 2. Delete "origin" category if empty or merge files

    for project in Project.objects.all():
        print(f"Cleaning up {project.name}...")

        # Merge "releases" -> "Releases"
        bad_cat = (
            FileCategory.objects.filter(
                name__iexact="releases", project=project, parent=None
            )
            .exclude(name="Releases")
            .first()
        )
        good_cat = FileCategory.objects.filter(
            name="Releases", project=project, parent=None
        ).first()

        if bad_cat:
            print(f"  Found '{bad_cat.name}', merging into 'Releases'...")
            if not good_cat:
                bad_cat.name = "Releases"
                bad_cat.save()
                good_cat = bad_cat
            else:
                # Move subcategories
                for sub in bad_cat.children.all():
                    sub.parent = good_cat
                    sub.save()
                # Move files
                for f in bad_cat.files.all():
                    f.category = good_cat
                    f.save()
                bad_cat.delete()

        # Handle "origin"
        origin_cat = FileCategory.objects.filter(
            name__iexact="origin", project=project
        ).first()
        if origin_cat:
            print(f"  Found 'origin' category, removing and unlinking files...")
            for f in origin_cat.files.all():
                f.category = None
                f.save()
            origin_cat.delete()

    print("Done.")


if __name__ == "__main__":
    cleanup_categories()
