from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator

from tasks.models import Project, ModuleMember
from ..models import ProjectFile, FileCategory, DocumentAccessRight


def check_file_access(pf, user, access_type="view"):
    if user.is_admin or getattr(user, 'is_project_manager', False):
        return True
    if pf.uploaded_by == user:
        return True
    if access_type in ["edit", "delete"]:
        if pf.project:
            if (pf.project.managers.filter(pk=user.pk).exists() or 
                pf.project.members.filter(pk=user.pk).exists()):
                return True
        if pf.file_type in ["document", "pdf", "code", "text"]:
            return pf.uploaded_by == user
    if access_type != "view":
        return False
    module = pf.module or (pf.task.module if pf.task else None)
    if module:
        return ModuleMember.objects.filter(module=module, user=user).exists()
    elif pf.project:
        return pf.project.members.filter(pk=user.pk).exists()
    return False


@login_required
def file_list(request):
    user = request.user
    search, type_filter, proj_filter, module_filter, resource_view, repo_cat_id = (
        request.GET.get("q", ""),
        request.GET.get("type", ""),
        request.GET.get("project", ""),
        request.GET.get("module", ""),
        request.GET.get("resource_view", "repository"),
        request.GET.get("repo_cat_id"),
    )
    if resource_view == "grid":
        resource_view = "repository"
    current_repo_cat = (
        get_object_or_404(FileCategory, pk=repo_cat_id, is_in_trash=False) if repo_cat_id else None
    )
    proj_id = request.GET.get("project", "")
    current_project, root_categories, uncategorized_files = (
        (get_object_or_404(Project, pk=proj_id) if proj_id else None),
        [],
        [],
    )
    if current_project and not current_repo_cat:
        root_categories = current_project.file_categories.filter(parent=None, is_in_trash=False).order_by(
            "name"
        )
        uncategorized_files = current_project.files.filter(category=None, is_in_trash=False).order_by(
            "original_name"
        )
    q_filter = (
        Q(uploaded_by=user)
        | Q(project__managers=user)
        | Q(project__members=user, is_public=True)
        | Q(project__members=user, module__isnull=True, task__module__isnull=True)
        | Q(module__members__user=user)
        | Q(task__module__members__user=user)
        | Q(access_rights__user=user, access_rights__can_view=True)
    )
    files = ProjectFile.objects.filter(q_filter, versions__isnull=True, is_in_trash=False).distinct()
    if search:
        files = files.filter(
            Q(original_name__icontains=search)
            | Q(title__icontains=search)
            | Q(description__icontains=search)
        )
    if type_filter:
        files = files.filter(file_type=type_filter)
    if proj_filter:
        files = files.filter(project_id=proj_filter)
    if module_filter:
        files = files.filter(module_id=module_filter)
    total_size = files.aggregate(s=Sum("file_size"))["s"] or 0
    stats = {
        "total": files.count(),
        "total_size": total_size,
        "images": files.filter(file_type="image").count(),
        "documents": files.filter(file_type__in=["document", "pdf"]).count(),
        "code": files.filter(file_type="code").count(),
        "archives": files.filter(file_type="archive").count(),
        "total_size_display": (
            f"{total_size / 1024:.1f} KB"
            if total_size < 1024**2
            else (
                f"{total_size / 1024**2:.1f} MB"
                if total_size < 1024**3
                else f"{total_size / 1024**3:.2f} GB"
            )
        ),
    }
    page_num = request.GET.get("page")
    page_obj = None

    files_no_project_qs = ProjectFile.objects.none()
    uncategorized_files_qs = ProjectFile.objects.none()
    latest_files_qs = ProjectFile.objects.none()

    if resource_view == "repository":
        if current_repo_cat:
            latest_files_qs = current_repo_cat.latest_files
            page_obj = Paginator(latest_files_qs, 20).get_page(page_num)
        elif current_project:
            uncategorized_files_qs = current_project.files.filter(category=None, is_in_trash=False).order_by("original_name")
            page_obj = Paginator(uncategorized_files_qs, 20).get_page(page_num)
        else:
            files_no_project_qs = ProjectFile.objects.filter(q_filter, project__isnull=True).distinct().order_by("original_name")
            page_obj = Paginator(files_no_project_qs, 20).get_page(page_num)

    return render(
        request,
        "files/file_list.html",
        {
            "files": page_obj,
            "page_obj": page_obj,
            "projects": Project.objects.filter(
                Q(managers=user) | Q(members=user)
            ).distinct(),
            "files_no_project": page_obj.object_list if not current_project and not current_repo_cat and resource_view == "repository" else files_no_project_qs,
            "stats": stats,
            "type_choices": ProjectFile.FILE_TYPE_CHOICES,
            "search": search,
            "type_filter": type_filter,
            "proj_filter": proj_filter,
            "resource_view": resource_view,
            "current_repo_cat": current_repo_cat,
            "current_project": current_project,
            "root_categories": root_categories,
            "uncategorized_files": page_obj.object_list if current_project and not current_repo_cat and resource_view == "repository" else uncategorized_files_qs,
            "latest_files": page_obj.object_list if current_repo_cat and resource_view == "repository" else latest_files_qs,
        },
    )


@login_required
def project_files(request, pk):
    project = get_object_or_404(Project, pk=pk)
    user = request.user
    type_filter, cat_filter, search = (
        request.GET.get("type", ""),
        request.GET.get("category", ""),
        request.GET.get("q", ""),
    )
    if not (
        project.members.filter(pk=user.pk).exists()
        or project.managers.filter(pk=user.pk).exists()
        or ModuleMember.objects.filter(module__project=project, user=user).exists()
    ):
        messages.error(request, "No access to project files.")
        return redirect("files:file_list")
    q_filter = (
        Q(uploaded_by=user)
        | Q(project__managers=user)
        | Q(project__members=user, is_public=True)
        | Q(project__members=user, module__isnull=True, task__module__isnull=True)
        | Q(module__members__user=user)
        | Q(task__module__members__user=user)
        | Q(access_rights__user=user, access_rights__can_view=True)
    )
    files = (
        project.files.filter(q_filter, versions__isnull=True, is_in_trash=False)
        .select_related("uploaded_by", "task", "category")
        .distinct()
    )
    if type_filter:
        files = files.filter(file_type=type_filter)
    if cat_filter:
        files = files.filter(category_id=cat_filter)
    if search:
        files = files.filter(
            Q(original_name__icontains=search) | Q(title__icontains=search)
        )
    recently_updated = (
        project.files.filter(is_in_trash=False)
        .select_related("uploaded_by", "category")
        .order_by("-updated_at")[:10]
    )
    return render(
        request,
        "files/project_files.html",
        {
            "project": project,
            "files": files.order_by("-created_at"),
            "root_categories": project.file_categories.filter(parent__isnull=True, is_in_trash=False),
            "categories": project.file_categories.filter(is_in_trash=False),
            "recently_updated": recently_updated,
            "stats": {
                "total": files.count(),
                "total_size": files.aggregate(s=Sum("file_size"))["s"] or 0,
                "by_type": [
                    {
                        "key": ft,
                        "label": label,
                        "count": files.filter(file_type=ft).count(),
                    }
                    for ft, label in ProjectFile.FILE_TYPE_CHOICES
                ],
            },
            "type_choices": ProjectFile.FILE_TYPE_CHOICES,
            "type_filter": type_filter,
            "cat_filter": cat_filter,
            "search": search,
        },
    )
