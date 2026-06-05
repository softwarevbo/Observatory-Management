from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from tasks.models import Project, ProjectModule, ModuleMember
from tasks.utils.query_utils import get_visible_notes_qs
from .models import KnowledgeBaseNote
from .forms import KnowledgeBaseNoteForm
from .services import KBService

"""
This module processes view controllers and workflows for the Notes / Knowledge Base.
Supports role-based read/write access checks, page routing list controllers, and trash workflows.
"""


def check_kb_access(kb, user, access_type="view"):
    """
    Validates user credentials against specific Knowledge Base access constraints.
    Grants access if the user is the author, an admin, a project manager,
    has explicit DocumentAccessRight, or belongs to the note's project module.
    """
    if kb.author == user:
        return True
    if not kb.project:
        return False
    if user.is_admin:
        return True
    if kb.project and (
        user.is_project_manager
        or kb.project.managers.filter(pk=user.pk).exists()
        or kb.project.project_incharge == user
    ):
        return True

    from files.models import DocumentAccessRight

    explicit = DocumentAccessRight.objects.filter(kb_note=kb, user=user).first()
    if explicit:
        if access_type == "view":
            return explicit.can_view
        if access_type == "edit":
            return explicit.can_edit
        if access_type == "delete":
            return explicit.can_delete

    if access_type != "view":
        return False

    if kb.module:
        return ModuleMember.objects.filter(module=kb.module, user=user).exists()
    elif kb.project:
        return kb.project.members.filter(pk=user.pk).exists()
    return False


@login_required
def kb_overview(request):
    """
    Renders the central index list of all visible Knowledge Base notes.
    Supports search filtering by text queries, authors, and projects.
    """
    notes = get_visible_notes_qs(request.user)
    q = request.GET.get("q", "")
    project_filter = request.GET.get("project", "")
    author_filter = request.GET.get("author", "")

    if q:
        notes = notes.filter(Q(title__icontains=q) | Q(content__icontains=q))
    if project_filter:
        notes = notes.filter(project_id=project_filter)
    if author_filter:
        notes = notes.filter(author_id=author_filter)

    from accounts.models import User

    accessible_projects = Project.objects.filter(
        Q(managers=request.user) | Q(members=request.user) | Q(project_incharge=request.user)
    ).distinct()
    authors = User.objects.filter(knowledgebasenote__isnull=False).distinct()

    current_project = None
    if project_filter:
        current_project = Project.objects.filter(id=project_filter).first()

    return render(
        request,
        "kb/kb_overview.html",
        {
            "notes": notes,
            "q": q,
            "projects": accessible_projects,
            "authors": authors,
            "project_filter": project_filter,
            "author_filter": author_filter,
            "project": current_project,
        },
    )


@login_required
def kb_create_global(request):
    """
    Renders creation form for a new global note, allowing linking it to select projects.
    Note synchronization to the Notes folder is handled inside note.save() model trigger.
    """
    if request.user.is_admin:
        projects = Project.objects.all().order_by("name")
    else:
        projects = (
            Project.objects.filter(Q(managers=request.user) | Q(members=request.user))
            .distinct()
            .order_by("name")
        )

    selected_project_id = str(request.GET.get("project") or "").strip()

    form = KnowledgeBaseNoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        note = form.save(commit=False)
        project_id = request.POST.get("project_id")
        if project_id:
            try:
                note.project = Project.objects.get(pk=project_id)
            except Project.DoesNotExist:
                note.project = None
        note.author = request.user
        note.save()  # Auto-triggers Markdown file generation
        messages.success(request, f'Note "{note.title}" created successfully.')
        return redirect("tasks:kb_overview")

    return render(
        request,
        "kb/kb_create_global.html",
        {"projects": projects, "form": form, "selected_project_id": selected_project_id},
    )


@login_required
def kb_list(request, pk):
    """
    Displays the catalog list of notes for a specific project.
    """
    project = get_object_or_404(Project, pk=pk)
    if not request.user.is_admin:
        if not (
            project.members.filter(pk=request.user.pk).exists()
            or project.managers.filter(pk=request.user.pk).exists()
            or project.project_incharge == request.user
        ):
            messages.error(request, "You do not have access to this project.")
            return redirect("tasks:project_list")
    notes = project.kb_notes.filter(is_in_trash=False)
    q = request.GET.get("q", "")
    if q:
        notes = notes.filter(Q(title__icontains=q) | Q(content__icontains=q))
    return render(
        request, "kb/kb_list.html", {"project": project, "notes": notes, "q": q}
    )


@login_required
def kb_create(request, pk):
    """
    Renders creation form for a new note scoped within a specific project/module.
    Note synchronization to the Notes folder is handled inside note.save() model trigger.
    """
    project = get_object_or_404(Project, pk=pk)
    module = None
    module_id = request.GET.get("module")
    if module_id:
        try:
            module = ProjectModule.objects.get(pk=module_id, project=project)
        except ProjectModule.DoesNotExist:
            module = None

    form = KnowledgeBaseNoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        note = form.save(commit=False)
        note.project = project
        if module:
            note.module = module
        note.author = request.user
        note.save()  # Auto-triggers Markdown file generation
        messages.success(
            request, f'Note "{note.title}" created in project "{project.name}".'
        )
        return redirect("tasks:kb_list", pk=project.pk)

    return render(
        request,
        "kb/kb_form.html",
        {
            "form": form,
            "project": project,
            "module": module,
            "title": "Create Note",
            "action": "Save Note",
        },
    )


@login_required
def kb_detail(request, pk):
    """
    Renders note metadata parameters and markdown content.
    """
    note = get_object_or_404(KnowledgeBaseNote, pk=pk)
    project = note.project
    if not check_kb_access(note, request.user, "view"):
        messages.error(request, "You do not have access to this note.")
        return redirect("tasks:project_list")
    return render(
        request, "kb/kb_detail.html", {"note": note, "project": project}
    )


@login_required
def kb_edit(request, pk):
    """
    Renders the update form for modifying notes.
    """
    note = get_object_or_404(KnowledgeBaseNote, pk=pk)
    project = note.project
    if not check_kb_access(note, request.user, "edit"):
        messages.error(request, "You do not have permission to edit this note.")
        return redirect("tasks:kb_detail", pk=pk)

    form = KnowledgeBaseNoteForm(request.POST or None, instance=note)
    if request.method == "POST" and form.is_valid():
        form.save()  # Auto-triggers file update and renames if title changed
        messages.success(request, "Note updated.")
        return redirect("tasks:kb_detail", pk=pk)

    return render(
        request,
        "kb/kb_form.html",
        {
            "form": form,
            "project": project,
            "module": note.module,
            "title": "Edit Note",
            "action": "Update Note",
        },
    )


@login_required
def kb_access(request, pk):
    """
    Manages user-specific permissions (can_view, can_edit, can_delete) on a note.
    """
    from accounts.models import User
    from files.models import DocumentAccessRight

    note = get_object_or_404(KnowledgeBaseNote, pk=pk)
    project = note.project

    if not (
        request.user.is_admin
        or note.author == request.user
        or (project and project.managers.filter(pk=request.user.pk).exists())
    ):
        messages.error(
            request, "Only managers, admins, and the author can manage access rights."
        )
        return redirect("tasks:kb_detail", pk=pk)

    access_rights = DocumentAccessRight.objects.filter(kb_note=note)
    all_users = User.objects.filter(is_active=True)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            user_id = request.POST.get("user_id")
            can_view = request.POST.get("can_view") == "on"
            can_edit = request.POST.get("can_edit") == "on"
            can_delete = request.POST.get("can_delete") == "on"
            if user_id:
                target_user = get_object_or_404(User, pk=user_id)
                ar, _ = DocumentAccessRight.objects.get_or_create(
                    kb_note=note, user=target_user
                )
                ar.can_view, ar.can_edit, ar.can_delete = can_view, can_edit, can_delete
                ar.save()
                messages.success(
                    request, f"Access rights updated for {target_user.display_name}."
                )
        elif action == "remove":
            ar_id = request.POST.get("access_id")
            if ar_id:
                DocumentAccessRight.objects.filter(pk=ar_id).delete()
                messages.success(request, "Access right removed.")
        return redirect("tasks:kb_access", pk=pk)

    return render(
        request,
        "kb/kb_access.html",
        {"note": note, "access_rights": access_rights, "all_users": all_users},
    )


@login_required
def kb_delete(request, pk):
    """
    Renders soft-deletion confirmation and handles moving notes to trash.
    The soft-deletion state is synchronized to the corresponding file via note.save().
    """
    note = get_object_or_404(KnowledgeBaseNote, pk=pk)
    project = note.project
    if not check_kb_access(note, request.user, "delete"):
        messages.error(request, "You do not have permission to delete this note.")
        return redirect("tasks:kb_detail", pk=pk)

    if request.method == "POST":
        title = note.title
        note.is_in_trash = True
        note.deleted_at = timezone.now()
        note.deleted_by = request.user
        note.save()  # Auto-triggers file trashing
        messages.success(request, f'Note "{title}" has been moved to trash.')
        return (
            redirect("tasks:kb_list", pk=project.pk)
            if project
            else redirect("tasks:kb_overview")
        )

    return render(
        request, "kb/kb_confirm_delete.html", {"note": note, "project": project}
    )


@login_required
def note_restore(request, pk):
    """
    Restores soft-deleted notes from trash.
    Synchronization is auto-triggered via note.save().
    """
    note = get_object_or_404(KnowledgeBaseNote, pk=pk)
    is_authorized = (request.user.is_admin or 
                     (note.project and note.project.is_manager(request.user)) or 
                     (note.project and note.project.is_incharge(request.user)) or 
                     note.author == request.user)
                     
    if not is_authorized:
        messages.error(request, "You don't have permission to restore this note.")
        return redirect("tasks:trash")
        
    note.is_in_trash = False
    note.deleted_at = None
    note.deleted_by = None
    note.save()  # Auto-triggers file restoration from trash
    messages.success(request, f"Note '{note.title}' restored.")
    return redirect("tasks:trash")


@login_required
def note_permanent_delete(request, pk):
    """
    Permanently deletes notes and their synchronized files from both database and physical disk storage.
    """
    note = get_object_or_404(KnowledgeBaseNote, pk=pk)
    if not (request.user.is_admin or request.user.is_project_manager or (note.project and note.project.is_manager(request.user))):
        messages.error(request, "Only managers can permanently delete notes.")
        return redirect("tasks:trash")
        
    note.delete()  # Custom delete() cleans up database and physical file
    messages.success(request, "Note permanently deleted from database.")
    return redirect("tasks:trash")
