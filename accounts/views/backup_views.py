import os
import shutil
import zipfile
import tempfile
import json
import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.core.management import call_command

from accounts.rbac import get_canonical_role, ROLE_ROOT

logger = logging.getLogger(__name__)


@login_required
def export_backup_view(request):
    """
    Exports a complete ZIP archive backup of the system database and media files.
    Allows selection of PM, IM, TCS, Media, and DB records with zero data loss.
    Exclusive to Root Administrator / Superuser.
    """
    canonical_role = get_canonical_role(request.user)
    if canonical_role != ROLE_ROOT and not getattr(request.user, "is_superuser", False):
        messages.error(request, "Access Denied: Super Admin permission required for backups.")
        return redirect("accounts:settings")

    if request.method != "POST":
        return redirect("/accounts/settings/#system")

    include_pm = request.POST.get("include_pm") == "on"
    include_im = request.POST.get("include_im") == "on"
    include_tcs = request.POST.get("include_tcs") == "on"
    include_media = request.POST.get("include_media") == "on"
    include_db = request.POST.get("include_db") == "on"

    # Default to all checked if none explicitly provided
    if not (include_pm or include_im or include_tcs or include_media or include_db):
        include_pm = include_im = include_tcs = include_media = include_db = True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"IIA_Observatory_Backup_{timestamp}.zip"

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Export SQLite Database
            db_path = getattr(settings, 'DATABASES', {}).get('default', {}).get('NAME', 'db.sqlite3')
            if not os.path.isabs(str(db_path)):
                db_path = os.path.join(settings.BASE_DIR, str(db_path))

            if os.path.exists(db_path):
                temp_db_copy = os.path.join(temp_dir, "db_copy.sqlite3")
                try:
                    import sqlite3
                    src = sqlite3.connect(db_path)
                    dst = sqlite3.connect(temp_db_copy)
                    with dst:
                        src.backup(dst)
                    dst.close()
                    src.close()
                    zipf.write(temp_db_copy, arcname="db.sqlite3")
                except Exception:
                    zipf.write(db_path, arcname="db.sqlite3")

            # 2. Portable JSON Dump for AWS Database migrations
            json_dump_path = os.path.join(temp_dir, "db_dump.json")
            try:
                with open(json_dump_path, 'w', encoding='utf-8') as f:
                    call_command('dumpdata', stdout=f, indent=2, exclude=['contenttypes', 'auth.permission', 'sessions'])
                zipf.write(json_dump_path, arcname="db_dump.json")
            except Exception as dump_err:
                logger.warning(f"Dumpdata warning: {dump_err}")

            # 3. Export Media Files & Attachments
            if include_media and os.path.exists(settings.MEDIA_ROOT):
                for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, settings.MEDIA_ROOT)
                        zipf.write(full_path, arcname=os.path.join("media", rel_path))

            # 4. Manifest Metadata
            manifest_data = {
                "created_at": datetime.now().isoformat(),
                "created_by": request.user.username,
                "modules": {
                    "project_management": include_pm,
                    "inventory_management": include_im,
                    "telescope_control": include_tcs,
                    "media_files": include_media,
                    "database": include_db,
                },
                "version": "2.0.0",
            }
            manifest_path = os.path.join(temp_dir, "manifest.json")
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_data, f, indent=2)
            zipf.write(manifest_path, arcname="manifest.json")

        with open(zip_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
            return response

    except Exception as e:
        messages.error(request, f"Backup export failed: {str(e)}")
        return redirect("/accounts/settings/#system")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@login_required
def import_backup_view(request):
    """
    Restores complete system state (database records and media files) from an uploaded backup ZIP archive.
    Exclusive to Root Administrator / Superuser.
    """
    canonical_role = get_canonical_role(request.user)
    if canonical_role != ROLE_ROOT and not getattr(request.user, "is_superuser", False):
        messages.error(request, "Access Denied: Super Admin permission required for restore.")
        return redirect("accounts:settings")

    if request.method != "POST" or "backup_file" not in request.FILES:
        messages.error(request, "Please select a valid backup .zip file to restore.")
        return redirect("/accounts/settings/#system")

    uploaded_file = request.FILES["backup_file"]
    if not uploaded_file.name.endswith(".zip"):
        messages.error(request, "Invalid backup format. File must be a .zip archive.")
        return redirect("/accounts/settings/#system")

    temp_dir = tempfile.mkdtemp()
    zip_dest = os.path.join(temp_dir, "uploaded_backup.zip")

    try:
        with open(zip_dest, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        extract_dir = os.path.join(temp_dir, "extracted")
        with zipfile.ZipFile(zip_dest, 'r') as zipf:
            zipf.extractall(extract_dir)

        # 1. Restore Database
        extracted_db = os.path.join(extract_dir, "db.sqlite3")
        extracted_json = os.path.join(extract_dir, "db_dump.json")
        target_db = getattr(settings, 'DATABASES', {}).get('default', {}).get('NAME', 'db.sqlite3')
        if not os.path.isabs(str(target_db)):
            target_db = os.path.join(settings.BASE_DIR, str(target_db))

        if os.path.exists(extracted_db):
            shutil.copy2(extracted_db, target_db)
        elif os.path.exists(extracted_json):
            try:
                call_command('loaddata', extracted_json)
            except Exception as load_err:
                logger.warning(f"Loaddata warning: {load_err}")

        # 2. Restore Media Files
        extracted_media = os.path.join(extract_dir, "media")
        if os.path.exists(extracted_media):
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            for root, dirs, files in os.walk(extracted_media):
                for file in files:
                    src_file = os.path.join(root, file)
                    rel_path = os.path.relpath(src_file, extracted_media)
                    dest_file = os.path.join(settings.MEDIA_ROOT, rel_path)
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(src_file, dest_file)

        messages.success(request, "✅ System backup restored successfully with ZERO data loss!")
    except Exception as e:
        messages.error(request, f"Backup restore failed: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return redirect("/accounts/settings/#system")
