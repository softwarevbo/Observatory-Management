import os
import io
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.http import FileResponse
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model

# PDF manipulation dependencies
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

from ..models import ProjectFile, FileCategory, FileComment
from ..forms import FileCommentForm, FileEditForm
from tasks.models import AuditLog, Project
from .file_list_views import check_file_access

"""
This module processes file detail views, online text edits, PDF canvas drawings,
folder discussions, and trash approvals operations.
"""

def _restore_category_ancestors(category, user=None):
    """
    Recursively restores parent folder nodes of a category from the trash.
    Ensures that when a nested file is restored, its parent directories are restored too.
    """
    from files.views.manage_views import _bulk_trash_category_tree
    parent = category
    any_overridden = False
    while parent:
        if parent.is_in_trash:
            active_cat = FileCategory.objects.filter(
                name=parent.name,
                parent=parent.parent,
                project=parent.project,
                is_in_trash=False
            ).first()
            if active_cat:
                _bulk_trash_category_tree(active_cat.pk, user or parent.deleted_by)
                active_cat.is_in_trash = True
                active_cat.deleted_at = timezone.now()
                active_cat.deleted_by = user or parent.deleted_by
                active_cat.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
                any_overridden = True

            parent.is_in_trash = False
            parent.deleted_at = None
            parent.deleted_by = None
            parent.save(update_fields=["is_in_trash", "deleted_at", "deleted_by"])
        parent = parent.parent
    return any_overridden


@login_required
def file_detail(request, pk):
    """
    Renders detailed information page for a file.
    Shows comments, revision versions list, and embeds text preview widgets if file is plain text.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if not check_file_access(pf, request.user, "view"):
        messages.error(request, "No access to this file.")
        return redirect("files:file_list")
        
    comment_form = FileCommentForm(request.POST or None)
    if request.method == "POST" and comment_form.is_valid():
        c = comment_form.save(commit=False)
        c.file, c.author = pf, request.user
        c.save()
        messages.success(request, "Comment added.")
        return redirect("files:file_detail", pk=pk)
        
    text_content = None
    if pf.is_text_viewable and pf.file_size < 500_000:
        try:
            with pf.file.open("r") as f:
                text_content = f.read()
        except:
            pass
            
    return render(
        request,
        "files/file_detail.html",
        {
            "file": pf,
            "comments": pf.comments.select_related("author").all(),
            "versions": pf.versions.all() if not pf.parent_file else [],
            "comment_form": comment_form,
            "text_content": text_content,
            "can_edit": check_file_access(pf, request.user, "edit"),
            "can_delete": check_file_access(pf, request.user, "delete"),
        },
    )


@login_required
def file_edit(request, pk):
    """
    Modifies file metadata fields. Logs changes to system Audit logs.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if not check_file_access(pf, request.user, "edit"):
        messages.error(request, "No permission to edit.")
        return redirect("files:file_detail", pk=pk)
        
    form = FileEditForm(request.POST or None, instance=pf)
    if request.method == "POST" and form.is_valid():
        pf = form.save(commit=False)
        pf.last_modified_by = request.user
        pf.save()
        
        # Log metadata modification
        AuditLog.objects.create(
            user=request.user,
            action_type="edit",
            module="file",
            entity_id=str(pf.pk),
            entity_name=pf.display_name,
            details=f"Project: {pf.project.name if pf.project else 'N/A'} | Metadata updated for file '{pf.display_name}'."
        )
        
        messages.success(request, f'"{pf.display_name}" updated.')
        return redirect("files:file_detail", pk=pk)
    return render(request, "files/file_edit.html", {"form": form, "file": pf})


@login_required
def file_delete(request, pk):
    """
    Performs soft-deletion of files. Moves files to trash, records details,
    and logs actions to system audits.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if not check_file_access(pf, request.user, "delete"):
        messages.error(request, "No permission to delete.")
        return redirect("files:file_detail", pk=pk)
        
    project = pf.project
    if request.method == "POST":
        name = pf.display_name
        pf.is_in_trash = True
        pf.deleted_at = timezone.now()
        pf.deleted_by = request.user
        pf.save()
        
        # Log deletion
        AuditLog.objects.create(
            user=request.user,
            action_type="delete",
            module="file",
            entity_id=str(pf.pk),
            entity_name=pf.display_name,
            details=f"File '{pf.display_name}' moved to trash."
        )
        messages.success(request, f'"{name}" moved to trash.')
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return (
            redirect("files:project_files", pk=project.pk)
            if project
            else redirect("files:file_list")
        )
    return render(request, "files/file_confirm_delete.html", {"file": pf})


@login_required
def file_content_edit(request, pk):
    """
    Online plain-text code/document editor.
    Permits direct edits to plain text files, saving changes back to disk storage.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if not check_file_access(pf, request.user, "edit") or not pf.is_text_viewable:
        messages.error(request, "No permission or file not editable.")
        return redirect("files:file_detail", pk=pk)

    if request.method == "POST":
        content = request.POST.get("content")
        if content is not None:
            from django.core.files.base import ContentFile
            pf.last_modified_by = request.user
            try:
                # Try direct local filesystem overwrite to prevent Django name suffixing
                file_path = pf.file.path
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                pf.file_size = os.path.getsize(file_path)
                pf.save(update_fields=["file_size", "updated_at", "last_modified_by"])
            except (AttributeError, NotImplementedError, IOError):
                # Fallback for cloud/custom storage backends
                filename = pf.original_name
                pf.file.save(filename, ContentFile(content), save=False)
                pf.file_size = pf.file.size
                pf.save(update_fields=["file_size", "updated_at", "last_modified_by"])

            messages.success(request, f'Content of "{pf.display_name}" updated.')
            
            # Log edits
            AuditLog.objects.create(
                user=request.user,
                action_type="edit",
                module="file",
                entity_id=str(pf.pk),
                entity_name=pf.display_name,
                details=f"Project: {pf.project.name if pf.project else 'N/A'} | Content of file '{pf.display_name}' edited via online editor."
            )
        return redirect("files:file_detail", pk=pk)

    return redirect("files:file_detail", pk=pk)


@login_required
def file_restore(request, pk):
    """
    Restores files from trash.
    Utilizes transaction blocks to restore folder structures along with the file.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    
    # Check permissions
    is_authorized = (
        request.user.is_admin 
        or request.user.is_project_manager 
        or pf.uploaded_by == request.user
        or (pf.project and (
            pf.project.is_manager(request.user)
            or pf.project.members.filter(pk=request.user.pk).exists()
        ))
    )
    if not is_authorized:
        messages.error(request, "No permission to restore.")
        return redirect("tasks:trash")

    overridden = False
    # Atomic restoration block
    with transaction.atomic():
        if pf.category:
            overridden = _restore_category_ancestors(pf.category, request.user)

        pf.is_in_trash = False
        pf.hidden_from_user_trash = False
        pf.deleted_at = None
        pf.deleted_by = None
        pf.save(update_fields=["is_in_trash", "hidden_from_user_trash", "deleted_at", "deleted_by", "updated_at"])

    if overridden:
        messages.success(
            request, 
            f'"{pf.display_name}" restored. Existing active folder(s) with conflicting names in the repository were overridden.'
        )
    else:
        messages.success(request, f'"{pf.display_name}" restored with its original path.')
    trash_cat_id = request.GET.get("trash_cat_id") or request.POST.get("trash_cat_id")
    if trash_cat_id:
        return redirect(f"{reverse('tasks:trash')}?trash_cat_id={trash_cat_id}")
    return redirect("tasks:trash")


@login_required
def file_permanent_delete(request, pk):
    """
    Deletes files permanently from disk.
    Requires double approval: both Admin and PM must approve before files are removed.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager):
        messages.error(request, "Only managers can approve permanent deletion.")
        return redirect("tasks:trash")
        
    if request.user.is_admin:
        pf.admin_approved_deletion = True
    
    if request.user.is_project_manager or (pf.project and pf.project.is_manager(request.user)):
        pf.pm_approved_deletion = True
        
    # Check double approval status
    if pf.admin_approved_deletion and pf.pm_approved_deletion:
        name = pf.display_name
        pf.file.delete(save=False) # Delete physical file from disk
        pf.delete() # Remove database record
        messages.success(request, f'"{name}" permanently deleted from disk.')
    else:
        pf.save()
        messages.success(request, "Deletion approved. Waiting for other party approval.")
        
    return redirect("tasks:trash")


@login_required
def file_hide_from_trash(request, pk):
    """
    Hides soft-deleted files from a user's trash view.
    """
    pf = get_object_or_404(ProjectFile, pk=pk)
    if pf.deleted_by != request.user and not request.user.is_admin:
        messages.error(request, "No permission.")
        return redirect("tasks:trash")
        
    pf.hidden_from_user_trash = True
    pf.save()
    messages.success(request, "Item removed from your trash view.")
    return redirect("tasks:trash")


def embed_pdf_annotations(pf, comments):
    """
    Draws highlights and comment numbers onto transparent PDF layers using ReportLab,
    merges them into the PDF, and appends a comments summary to the bottom of the page.
    """
    try:
        # Load binary file data safely
        try:
            with open(pf.file.path, 'rb') as f:
                original_pdf_data = f.read()
        except (AttributeError, NotImplementedError, OSError):
            pf.file.seek(0)
            original_pdf_data = pf.file.read()
            pf.file.seek(0)
            
        reader = PdfReader(io.BytesIO(original_pdf_data))
        writer = PdfWriter()
        
        # Loop through pages to apply comments and annotations
        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            
            # Filter comments left on this page
            if hasattr(comments, "filter"):
                page_comments = comments.filter(page_number=page_num, parent__isnull=True)
            else:
                page_comments = [c for c in comments if c.page_number == page_num and c.parent_id is None]
            
            has_valid_comments = False
            for c in page_comments:
                if c.annotation_coords:
                    has_valid_comments = True
                    break
                    
            if has_valid_comments:
                box = page.mediabox
                page_width = float(box.width)
                page_height = float(box.height)
                
                # Create a transparent PDF layer to draw on
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                
                comment_index = 1
                for c in page_comments:
                    if c.annotation_coords:
                        try:
                            # Load coordinates JSON string
                            coords_list = json.loads(c.annotation_coords)
                            if isinstance(coords_list, dict):
                                coords_list = [coords_list]
                                
                            color_hex = c.highlight_color or "#ffeb3b"
                            try:
                                r_color = HexColor(color_hex)
                            except:
                                r_color = HexColor("#ffeb3b")
                                
                            # Configure highlight transparency
                            can.setFillColor(r_color)
                            can.setFillAlpha(0.35)
                            
                            first_rect = None
                            for rect in coords_list:
                                if not isinstance(rect, dict):
                                    continue
                                rx = rect.get("x", 0) * page_width
                                ry = (1.0 - rect.get("y", 0) - rect.get("h", 0)) * page_height
                                rw = rect.get("w", 0) * page_width
                                rh = rect.get("h", 0) * page_height
                                can.rect(rx, ry, rw, rh, fill=True, stroke=False)
                                
                                # Add standard text annotation box
                                try:
                                    can.textAnnotation(
                                        c.content,
                                        Rect=(rx, ry, rx + rw, ry + rh)
                                    )
                                except Exception as tae:
                                    print("Error creating text annotation:", tae)
                                if first_rect is None:
                                    first_rect = (rx, ry + rh)
                                    
                            # Draw comment numbers on highlight start coordinates
                            if first_rect:
                                can.setFillAlpha(1.0)
                                can.setFillColor(HexColor("#333333"))
                                can.setFont("Helvetica-Bold", 8)
                                can.drawString(first_rect[0] - 8, first_rect[1] + 2, f"[{comment_index}]")
                                comment_index += 1
                        except Exception as ce:
                            print("Error processing comment annotation:", ce)
                
                # Write a summary of page comments at the bottom of the page
                if comment_index > 1:
                    y_pos = 20
                    can.setFillAlpha(1.0)
                    can.setFillColor(HexColor("#333333"))
                    can.setFont("Helvetica-Bold", 7)
                    can.drawString(30, y_pos, "Page Annotations:")
                    y_pos -= 8
                    
                    comment_index = 1
                    for c in page_comments:
                        if c.annotation_coords:
                            comment_text = f"[{comment_index}] {c.author.display_name}: {c.content}"
                            if len(comment_text) > 120:
                                comment_text = comment_text[:117] + "..."
                            can.setFont("Helvetica", 6)
                            can.drawString(30, y_pos, comment_text)
                            y_pos -= 7
                            comment_index += 1
                            if y_pos < 5:
                                break
                                
                can.save()
                packet.seek(0)
                
                highlight_reader = PdfReader(packet)
                if len(highlight_reader.pages) > 0:
                    page.merge_page(highlight_reader.pages[0])
                    
            writer.add_page(page)
            
        out_buffer = io.BytesIO()
        writer.write(out_buffer)
        out_buffer.seek(0)
        
        response = FileResponse(out_buffer, content_type="application/pdf")
        name_part, ext = os.path.splitext(pf.original_name)
        annotated_name = f"{name_part}_annotated{ext}"
        response["Content-Disposition"] = f'attachment; filename="{annotated_name}"'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            pf.file.seek(0)
            return FileResponse(pf.file.open("rb"), as_attachment=True, filename=pf.original_name)
        except Exception as e2:
            print("Fallback download failed:", e2)
            raise e


@login_required
def document_discussion(request, project_id, doc_id):
    """
    Renders the discussion thread, annotations lists, and version history logs for a file.
    Supports comments with page numbers and highlights on PDFs.
    """
    pf = get_object_or_404(ProjectFile, pk=doc_id)
    if not check_file_access(pf, request.user, "view"):
        messages.error(request, "No access to this document.")
        return redirect("tasks:dashboard")

    download_opt = request.GET.get("download")
    if download_opt == "without_annotations":
        from django.http import FileResponse
        try:
            return FileResponse(pf.file.open("rb"), as_attachment=True, filename=pf.original_name)
        except Exception as e:
            messages.error(request, f"Could not download file: {e}")
            return redirect("tasks:document_discussion", project_id=project_id, doc_id=doc_id)
            
    elif download_opt == "with_annotations":
        if not pf.is_pdf:
            messages.error(request, "Only PDF files can be downloaded with annotations.")
            return redirect("tasks:document_discussion", project_id=project_id, doc_id=doc_id)
        comments = pf.comments.select_related("author").all()
        return embed_pdf_annotations(pf, comments)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_comment":
            content = request.POST.get("content")
            page_number = request.POST.get("page_number")
            section = request.POST.get("section", "")
            highlight_color = request.POST.get("highlight_color", "#ffeb3b")
            annotation_coords = request.POST.get("annotation_coords", "")
            assigned_to_id = request.POST.get("assigned_to")

            assigned_to = None
            if assigned_to_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                assigned_to = User.objects.filter(pk=assigned_to_id).first()

            c = FileComment.objects.create(
                file=pf,
                author=request.user,
                content=content,
                page_number=int(page_number) if page_number and page_number.isdigit() else None,
                section=section,
                highlight_color=highlight_color,
                annotation_coords=annotation_coords,
                assigned_to=assigned_to
            )

            # Send notification to assigned user
            if assigned_to and assigned_to != request.user:
                from notifications.models import Notification
                Notification.objects.create(
                    user=assigned_to,
                    title="Assigned to Annotation Comment",
                    content=f"{request.user.display_name} assigned you to a comment on document {pf.display_name}.",
                    link=reverse("tasks:document_discussion", kwargs={"project_id": project_id, "doc_id": doc_id}) + f"?comment_id={c.pk}"
                )

            # Log comment creation
            AuditLog.objects.create(
                user=request.user,
                action_type="create",
                module="file",
                entity_id=str(pf.pk),
                entity_name=pf.display_name,
                details=f"Added annotation comment on page {page_number or 'N/A'} of file '{pf.display_name}'."
            )

            # AJAX response rendering
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                comments = pf.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
                all_comments = pf.comments.select_related("author").all()
                versions = pf.versions.all().select_related("uploaded_by") if not pf.parent_file else []
                project_members = pf.project.members.all() if pf.project else get_user_model().objects.all()
                text_content = None
                if pf.is_text_viewable and pf.file_size < 500_000:
                    try:
                        with pf.file.open("r") as f:
                            text_content = f.read()
                    except:
                        pass
                return render(
                    request,
                    "files/document_discussion.html",
                    {
                        "project": pf.project,
                        "file": pf,
                        "comments": comments,
                        "all_comments": all_comments,
                        "versions": versions,
                        "project_members": project_members,
                        "text_content": text_content,
                        "can_edit": check_file_access(pf, request.user, "edit"),
                        "can_delete": check_file_access(pf, request.user, "delete"),
                    },
                )

            messages.success(request, "Comment added.")
            return redirect("tasks:document_discussion", project_id=project_id, doc_id=doc_id)

        elif action == "reply":
            parent_id = request.POST.get("parent_id")
            content = request.POST.get("content")
            parent_comment = get_object_or_404(FileComment, pk=parent_id, file=pf)

            FileComment.objects.create(
                file=pf,
                author=request.user,
                content=content,
                parent=parent_comment
            )

            # Notify parent comment author
            if parent_comment.author != request.user:
                from notifications.models import Notification
                Notification.objects.create(
                    user=parent_comment.author,
                    title="Reply to Document Comment",
                    content=f"{request.user.display_name} replied to your comment on {pf.display_name}.",
                    link=reverse("tasks:document_discussion", kwargs={"project_id": project_id, "doc_id": doc_id}) + f"?comment_id={parent_comment.pk}"
                )

            # Notify comment assignee if set
            if parent_comment.assigned_to and parent_comment.assigned_to != request.user and parent_comment.assigned_to != parent_comment.author:
                from notifications.models import Notification
                Notification.objects.create(
                    user=parent_comment.assigned_to,
                    title="Reply to Assigned Document Comment",
                    content=f"{request.user.display_name} replied to an assigned comment on {pf.display_name}.",
                    link=reverse("tasks:document_discussion", kwargs={"project_id": project_id, "doc_id": doc_id}) + f"?comment_id={parent_comment.pk}"
                )

            # AJAX response rendering
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                comments = pf.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
                all_comments = pf.comments.select_related("author").all()
                versions = pf.versions.all().select_related("uploaded_by") if not pf.parent_file else []
                project_members = pf.project.members.all() if pf.project else get_user_model().objects.all()
                text_content = None
                if pf.is_text_viewable and pf.file_size < 500_000:
                    try:
                        with pf.file.open("r") as f:
                            text_content = f.read()
                    except:
                        pass
                return render(
                    request,
                    "files/document_discussion.html",
                    {
                        "project": pf.project,
                        "file": pf,
                        "comments": comments,
                        "all_comments": all_comments,
                        "versions": versions,
                        "project_members": project_members,
                        "text_content": text_content,
                        "can_edit": check_file_access(pf, request.user, "edit"),
                        "can_delete": check_file_access(pf, request.user, "delete"),
                    },
                )

            messages.success(request, "Reply added.")
            return redirect("tasks:document_discussion", project_id=project_id, doc_id=doc_id)

        elif action == "update_assignment":
            comment_id = request.POST.get("comment_id")
            assigned_to_id = request.POST.get("assigned_to")
            comment = get_object_or_404(FileComment, pk=comment_id, file=pf)

            assigned_to = None
            if assigned_to_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                assigned_to = User.objects.filter(pk=assigned_to_id).first()

            old_assignee = comment.assigned_to
            comment.assigned_to = assigned_to
            comment.save()

            # Notify new assignee
            if assigned_to and assigned_to != request.user and assigned_to != old_assignee:
                from notifications.models import Notification
                Notification.objects.create(
                    user=assigned_to,
                    title="Assigned to Comment Thread",
                    content=f"{request.user.display_name} assigned you to a comment thread on {pf.display_name}.",
                    link=reverse("tasks:document_discussion", kwargs={"project_id": project_id, "doc_id": doc_id}) + f"?comment_id={comment.pk}"
                )

            # AJAX response rendering
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                comments = pf.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
                all_comments = pf.comments.select_related("author").all()
                versions = pf.versions.all().select_related("uploaded_by") if not pf.parent_file else []
                project_members = pf.project.members.all() if pf.project else get_user_model().objects.all()
                text_content = None
                if pf.is_text_viewable and pf.file_size < 500_000:
                    try:
                        with pf.file.open("r") as f:
                            text_content = f.read()
                    except:
                        pass
                return render(
                    request,
                    "files/document_discussion.html",
                    {
                        "project": pf.project,
                        "file": pf,
                        "comments": comments,
                        "all_comments": all_comments,
                        "versions": versions,
                        "project_members": project_members,
                        "text_content": text_content,
                        "can_edit": check_file_access(pf, request.user, "edit"),
                        "can_delete": check_file_access(pf, request.user, "delete"),
                    },
                )

            messages.success(request, "Assignment updated.")
            return redirect("tasks:document_discussion", project_id=project_id, doc_id=doc_id)

    project_members = []
    if pf.project:
        project_members = pf.project.members.all()
    else:
        from django.contrib.auth import get_user_model
        project_members = get_user_model().objects.all()

    comments = pf.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
    all_comments = pf.comments.select_related("author").all()
    versions = pf.versions.all().select_related("uploaded_by") if not pf.parent_file else []
    project = pf.project

    text_content = None
    if pf.is_text_viewable and pf.file_size < 500_000:
        try:
            with pf.file.open("r") as f:
                text_content = f.read()
        except:
            pass

    return render(
        request,
        "files/document_discussion.html",
        {
            "project": project,
            "file": pf,
            "comments": comments,
            "all_comments": all_comments,
            "versions": versions,
            "project_members": project_members,
            "text_content": text_content,
            "can_edit": check_file_access(pf, request.user, "edit"),
            "can_delete": check_file_access(pf, request.user, "delete"),
        },
    )


@login_required
def folder_discussion(request, project_id, folder_id):
    """
    Renders discussion threads inside folder modules.
    Matches features from files discussions, including comments, assignees, and replies.
    """
    project = get_object_or_404(Project, pk=project_id)
    folder = get_object_or_404(FileCategory, pk=folder_id, project=project)
    
    # Permission verification
    if not (request.user.is_admin or getattr(request.user, 'is_project_manager', False) or 
            project.managers.filter(pk=request.user.pk).exists() or 
            project.members.filter(pk=request.user.pk).exists() or 
            folder.created_by == request.user):
        messages.error(request, "No access to this folder's discussion.")
        return redirect("files:project_files", pk=project.pk)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_comment":
            content = request.POST.get("content")
            section = request.POST.get("section", "")
            assigned_to_id = request.POST.get("assigned_to")

            assigned_to = None
            if assigned_to_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                assigned_to = User.objects.filter(pk=assigned_to_id).first()

            c = FileComment.objects.create(
                category=folder,
                author=request.user,
                content=content,
                section=section,
                assigned_to=assigned_to
            )

            # Notify assignee
            if assigned_to and assigned_to != request.user:
                from notifications.models import Notification
                Notification.objects.create(
                    user=assigned_to,
                    title="Assigned to Folder Comment",
                    content=f"{request.user.display_name} assigned you to a comment on folder {folder.name}.",
                    link=reverse("tasks:folder_discussion", kwargs={"project_id": project_id, "folder_id": folder_id}) + f"?comment_id={c.pk}"
                )

            # Log folder commentary creation
            AuditLog.objects.create(
                user=request.user,
                action_type="create",
                module="folder",
                entity_id=str(folder.pk),
                entity_name=folder.name,
                details=f"Added comment on folder '{folder.name}'."
            )

            # AJAX response rendering
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                comments = folder.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
                all_comments = folder.comments.select_related("author").all()
                project_members = project.members.all()
                return render(
                    request,
                    "files/document_discussion.html",
                    {
                        "project": project,
                        "folder": folder,
                        "comments": comments,
                        "all_comments": all_comments,
                        "project_members": project_members,
                        "can_delete": request.user.is_admin or getattr(request.user, 'is_project_manager', False) or folder.created_by == request.user,
                    },
                )

            messages.success(request, "Comment added.")
            return redirect("tasks:folder_discussion", project_id=project_id, folder_id=folder_id)

        elif action == "reply":
            parent_id = request.POST.get("parent_id")
            content = request.POST.get("content")
            parent_comment = get_object_or_404(FileComment, pk=parent_id, category=folder)

            FileComment.objects.create(
                category=folder,
                author=request.user,
                content=content,
                parent=parent_comment
            )

            # Notify parent comment author
            if parent_comment.author != request.user:
                from notifications.models import Notification
                Notification.objects.create(
                    user=parent_comment.author,
                    title="Reply to Folder Comment",
                    content=f"{request.user.display_name} replied to your comment on folder {folder.name}.",
                    link=reverse("tasks:folder_discussion", kwargs={"project_id": project_id, "folder_id": folder_id}) + f"?comment_id={parent_comment.pk}"
                )

            # AJAX response rendering
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                comments = folder.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
                all_comments = folder.comments.select_related("author").all()
                project_members = project.members.all()
                return render(
                    request,
                    "files/document_discussion.html",
                    {
                        "project": project,
                        "folder": folder,
                        "comments": comments,
                        "all_comments": all_comments,
                        "project_members": project_members,
                        "can_delete": request.user.is_admin or getattr(request.user, 'is_project_manager', False) or folder.created_by == request.user,
                    },
                )

            messages.success(request, "Reply added.")
            return redirect("tasks:folder_discussion", project_id=project_id, folder_id=folder_id)

        elif action == "update_assignment":
            comment_id = request.POST.get("comment_id")
            assigned_to_id = request.POST.get("assigned_to")
            comment = get_object_or_404(FileComment, pk=comment_id, category=folder)

            assigned_to = None
            if assigned_to_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                assigned_to = User.objects.filter(pk=assigned_to_id).first()

            old_assignee = comment.assigned_to
            comment.assigned_to = assigned_to
            comment.save()

            # Notify new assignee
            if assigned_to and assigned_to != request.user and assigned_to != old_assignee:
                from notifications.models import Notification
                Notification.objects.create(
                    user=assigned_to,
                    title="Assigned to Folder Comment Thread",
                    content=f"{request.user.display_name} assigned you to a comment thread on folder {folder.name}.",
                    link=reverse("tasks:folder_discussion", kwargs={"project_id": project_id, "folder_id": folder_id}) + f"?comment_id={comment.pk}"
                )

            # AJAX response rendering
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                comments = folder.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
                all_comments = folder.comments.select_related("author").all()
                project_members = project.members.all()
                return render(
                    request,
                    "files/document_discussion.html",
                    {
                        "project": project,
                        "folder": folder,
                        "comments": comments,
                        "all_comments": all_comments,
                        "project_members": project_members,
                        "can_delete": request.user.is_admin or getattr(request.user, 'is_project_manager', False) or folder.created_by == request.user,
                    },
                )

            messages.success(request, "Assignment updated.")
            return redirect("tasks:folder_discussion", project_id=project_id, folder_id=folder_id)

    project_members = project.members.all()
    comments = folder.comments.filter(parent__isnull=True).select_related("author", "assigned_to").prefetch_related("replies__author")
    all_comments = folder.comments.select_related("author").all()

    return render(
        request,
        "files/document_discussion.html",
        {
            "project": project,
            "folder": folder,
            "comments": comments,
            "all_comments": all_comments,
            "project_members": project_members,
            "can_delete": request.user.is_admin or getattr(request.user, 'is_project_manager', False) or folder.created_by == request.user,
        },
    )
