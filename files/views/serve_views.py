import mimetypes
import zipfile
import io
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from ..models import ProjectFile, FileCategory
from .file_list_views import check_file_access

"""
This module contains views designed to serve and download files and folders.
"""

@login_required
def file_download(request, pk):
    """
    Streams a single file attachment down to the client.
    Safe-updates the hit count by leveraging update() directly, which avoids race conditions.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if not check_file_access(pf, request.user, "view"):
        raise Http404
    
    # Increment the download counts
    ProjectFile.objects.filter(pk=pk).update(download_count=pf.download_count + 1)
    try:
        return FileResponse(
            pf.file.open("rb"), as_attachment=True, filename=pf.original_name
        )
    except:
        raise Http404("File not found on server.")


@login_required
def file_view(request, pk):
    """
    Serves files inline for rendering within browser frames (e.g. PDF previews).
    Explicitly checks extension types to define content type headers.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if not check_file_access(pf, request.user, "view"):
        raise Http404
    try:
        ext = (pf.extension or "").lower().lstrip(".")
        # Map common extensions to their explicit MIME types
        explicit_mime = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "svg": "image/svg+xml",
            "mp4": "video/mp4",
            "webm": "video/webm",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "txt": "text/plain; charset=utf-8",
            "md": "text/plain; charset=utf-8",
            "html": "text/html; charset=utf-8",
        }
        mime = (
            explicit_mime.get(ext)
            or mimetypes.guess_type(pf.original_name)[0]
            or "application/octet-stream"
        )
        response = FileResponse(pf.file.open("rb"), content_type=mime)
        response["Content-Disposition"], response["X-Frame-Options"] = (
            f'inline; filename="{pf.original_name}"',
            "SAMEORIGIN",
        )
        return response
    except:
        raise Http404("File not found on server.")


@login_required
def download_folder(request, pk):
    """
    Packages a directory category and all its nested subfolders recursively into a ZIP archive,
    then streams the binary dataset directly back to the client.
    """
    category = get_object_or_404(FileCategory, pk=pk)
    
    # Verify project-level user authorization
    if category.project:
        if not (category.project.members.filter(pk=request.user.pk).exists() or
                category.project.managers.filter(pk=request.user.pk).exists() or
                request.user.is_admin or request.user.is_project_manager):
            raise Http404

    buffer = io.BytesIO()
    # Compress files inside category recursively
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        def add_category_to_zip(cat, base_path=""):
            # Fetch primary files (versions__isnull=True) that are not in the trash
            for f in cat.files.filter(is_in_trash=False, versions__isnull=True):
                if check_file_access(f, request.user, "view"):
                    try:
                        file_data = f.file.read()
                        zipf.writestr(f"{base_path}{f.original_name}", file_data)
                    except:
                        pass
            # Walk down sub-directories recursively
            for child in cat.children.filter(is_in_trash=False):
                add_category_to_zip(child, f"{base_path}{child.name}/")
                
        add_category_to_zip(category, f"{category.name}/")
        
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{category.name}.zip"'
    return response
