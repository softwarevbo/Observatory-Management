from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count, Case, When, IntegerField
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator

from tasks.models import Project, ModuleMember
from ..models import ProjectFile, FileCategory, DocumentAccessRight

"""
This module processes primary files and folders listing, sorting, and authorization checks.
"""

def check_file_access(pf, user, access_type="view"):
    """
    Validates user credentials against file parameters:
    - Admins/PMs have access to all items.
    - Creators have full control over their uploaded files.
    - Viewers must belong to linked projects/modules or have explicit overrides.
    """
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
    """
    Main directory controller page supporting different layouts (tree, grid, repository views).
    Calculates storage metrics in a single database lookup using conditional aggregation,
    and sorts the folder structure to group categories and files recursively.
    """
    user = request.user
    
    # Load session preferences (default to tree)
    saved_view = request.session.get("file_view_preference", "tree")
    resource_view = request.GET.get("resource_view")
    if resource_view:
        request.session["file_view_preference"] = resource_view
    else:
        resource_view = saved_view

    search, type_filter, proj_filter, module_filter, repo_cat_id = (
        request.GET.get("q", ""),
        request.GET.get("type", ""),
        request.GET.get("project", ""),
        request.GET.get("module", ""),
        request.GET.get("repo_cat_id"),
    )

    # Sorting options mapping
    sort = request.GET.get("sort", "name_asc")
    SORT_MAP = {
        "name_asc":      "original_name",
        "name_desc":     "-original_name",
        "size_desc":     "-file_size",
        "size_asc":      "file_size",
        "modified_desc": "-updated_at",
        "modified_asc":  "updated_at",
        "created_desc":  "-created_at",
        "created_asc":   "created_at",
        "type_asc":      "file_type",
    }
    sort_field = SORT_MAP.get(sort, "original_name")
    current_repo_cat = (
        get_object_or_404(FileCategory, pk=repo_cat_id, is_in_trash=False) if repo_cat_id else None
    )
    proj_id = request.GET.get("project", "")
    current_project, root_categories, uncategorized_files = (
        (get_object_or_404(Project, pk=proj_id) if proj_id else None),
        [],
        [],
    )
    
    # Base user visibility filter parameters
    q_filter = (
        Q(uploaded_by=user)
        | Q(project__managers=user)
        | Q(project__members=user, is_public=True)
        | Q(project__members=user, module__isnull=True, task__module__isnull=True)
        | Q(module__members__user=user)
        | Q(task__module__members__user=user)
        | Q(access_rights__user=user, access_rights__can_view=True)
    )
    
    # Filter out trash and version revisions (versions__isnull=True represents primary files)
    files = ProjectFile.objects.filter(q_filter, versions__isnull=True, is_in_trash=False).distinct().order_by(sort_field)
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
        
    # Single-Query Conditional Aggregation computing global counts
    agg = files.aggregate(
        total=Count('pk'),
        total_size=Sum('file_size'),
        images=Count(Case(When(file_type='image', then=1), output_field=IntegerField())),
        documents=Count(Case(When(file_type__in=['document', 'pdf'], then=1), output_field=IntegerField())),
        code=Count(Case(When(file_type='code', then=1), output_field=IntegerField())),
        archives=Count(Case(When(file_type='archive', then=1), output_field=IntegerField())),
    )
    total_size = agg['total_size'] or 0
    stats = {
        "total": agg['total'],
        "total_size": total_size,
        "images": agg['images'],
        "documents": agg['documents'],
        "code": agg['code'],
        "archives": agg['archives'],
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

    # Personal untrashed files
    personal_files_base = ProjectFile.objects.filter(
        q_filter, project__isnull=True, versions__isnull=True, is_in_trash=False
    ).distinct().order_by(sort_field)

    # Fetch 5 most recently updated records
    recent_files_qs = ProjectFile.objects.filter(q_filter, versions__isnull=True, is_in_trash=False)
    if proj_filter:
        recent_files_qs = recent_files_qs.filter(project_id=proj_filter)
    recent_files = recent_files_qs.select_related('project', 'uploaded_by', 'category').order_by('-updated_at')[:5]

    # Paginate list objects based on view layout preferences
    if resource_view == "repository":
        if current_repo_cat:
            latest_files_qs = current_repo_cat.latest_files
            if sort_field != "original_name":
                latest_files_qs = latest_files_qs.order_by(sort_field)
            page_obj = Paginator(latest_files_qs, 20).get_page(page_num)
        elif current_project:
            uncategorized_files_qs = current_project.files.filter(
                category=None, versions__isnull=True, is_in_trash=False
            ).order_by(sort_field)
            page_obj = Paginator(uncategorized_files_qs, 20).get_page(page_num)
        else:
            files_no_project_qs = personal_files_base
            page_obj = Paginator(files_no_project_qs, 20).get_page(page_num)
    elif resource_view == "grid":
        page_obj = Paginator(files, 20).get_page(page_num)
    else:
        files_no_project_qs = personal_files_base

    # Pre-fetch relations to avoid N+1 queries during rendering
    projects_qs = (
        Project.objects.filter(Q(managers=user) | Q(members=user))
        .distinct()
        .prefetch_related(
            'files',
            'file_categories',
            'file_categories__children',
            'file_categories__children__children',
            'managers',
            'members',
        )
    )
    if proj_filter:
        projects_qs = projects_qs.filter(pk=proj_filter)

    # ── Sort hierarchy of categories & files for Windows/Ubuntu style view ──
    project_ids = list(projects_qs.values_list('pk', flat=True))

    CAT_SORT_MAP = {
        "name_asc":      "name",
        "name_desc":     "-name",
        "size_desc":     "name",
        "size_asc":      "name",
        "modified_desc": "-created_at",
        "modified_asc":  "created_at",
        "created_desc":  "-created_at",
        "created_asc":   "created_at",
        "type_asc":      "name",
    }
    cat_sort_field = CAT_SORT_MAP.get(sort, "name")

    all_files_for_tree = list(ProjectFile.objects.filter(
        project_id__in=project_ids,
        versions__isnull=True,
        is_in_trash=False
    ).distinct().order_by(sort_field))

    # Determine case-insensitive category sort expression (mirrors OS filesystem ordering)
    if cat_sort_field == 'name':
        _cat_order_expr = Lower('name')
    elif cat_sort_field == '-name':
        _cat_order_expr = Lower('name').desc()
    else:
        _cat_order_expr = cat_sort_field

    all_categories_for_tree = list(FileCategory.objects.filter(
        project_id__in=project_ids,
        is_in_trash=False
    ).distinct().order_by(_cat_order_expr))

    # Calculate directory storage sizes recursively
    cat_parents = {cat.pk: cat.parent_id for cat in all_categories_for_tree}
    category_sizes = {cat.pk: 0 for cat in all_categories_for_tree}
    for f in all_files_for_tree:
        if f.category_id:
            curr = f.category_id
            while curr in category_sizes:
                category_sizes[curr] += f.file_size
                curr = cat_parents.get(curr)

    # Sort categories based on size properties if requested
    if sort in ["size_desc", "size_asc"]:
        sorted_cats = sorted(
            all_categories_for_tree,
            key=lambda c: category_sizes.get(c.pk, 0),
            reverse=(sort == "size_desc")
        )
    else:
        sorted_cats = list(all_categories_for_tree)

    # Group categories and files into directories
    project_root_cats = {pid: [] for pid in project_ids}
    project_root_files = {pid: [] for pid in project_ids}
    cat_children = {cat.pk: [] for cat in all_categories_for_tree}
    cat_files = {cat.pk: [] for cat in all_categories_for_tree}

    for cat in sorted_cats:
        size_in_bytes = category_sizes.get(cat.pk, 0)
        if size_in_bytes < 1024:
            cat.temp_size_display = f"{size_in_bytes} B"
        elif size_in_bytes < 1024**2:
            cat.temp_size_display = f"{size_in_bytes / 1024:.1f} KB"
        else:
            cat.temp_size_display = f"{size_in_bytes / 1024**2:.1f} MB"

        if cat.parent_id:
            if cat.parent_id in cat_children:
                cat_children[cat.parent_id].append(cat)
        else:
            if cat.project_id in project_root_cats:
                project_root_cats[cat.project_id].append(cat)

    for f in all_files_for_tree:
        if f.category_id:
            if f.category_id in cat_files:
                cat_files[f.category_id].append(f)
        else:
            if f.project_id in project_root_files:
                project_root_files[f.project_id].append(f)

    # Bind lists to attributes for simple template iterations
    for cat in all_categories_for_tree:
        cat.temp_children = cat_children[cat.pk]
        cat.temp_files = cat_files[cat.pk]

    for p in projects_qs:
        p.temp_categories = project_root_cats.get(p.pk, [])
        p.temp_files = project_root_files.get(p.pk, [])

    if current_project and not current_repo_cat:
        root_categories = project_root_cats.get(current_project.pk, [])
        uncategorized_files = project_root_files.get(current_project.pk, [])

    if current_repo_cat:
        match = next((c for c in all_categories_for_tree if c.pk == current_repo_cat.pk), None)
        if match:
            current_repo_cat.temp_children = match.temp_children
            current_repo_cat.temp_files = match.temp_files
            current_repo_cat.temp_size_display = match.temp_size_display
        else:
            current_repo_cat.temp_children = []
            current_repo_cat.temp_files = []
            current_repo_cat.temp_size_display = "0 B"

    return render(
        request,
        "files/file_list.html",
        {
            "files": page_obj,
            "page_obj": page_obj,
            "projects": projects_qs,
            "files_no_project": (
                page_obj.object_list
                if (not current_project and not current_repo_cat and resource_view == "repository")
                else files_no_project_qs
            ),
            "stats": stats,
            "type_choices": ProjectFile.FILE_TYPE_CHOICES,
            "search": search,
            "type_filter": type_filter,
            "proj_filter": proj_filter,
            "module_filter": module_filter,
            "resource_view": resource_view,
            "sort": sort,
            "current_repo_cat": current_repo_cat,
            "current_project": current_project,
            "root_categories": root_categories,
            "uncategorized_files": (
                page_obj.object_list
                if (current_project and not current_repo_cat and resource_view == "repository")
                else uncategorized_files_qs
            ),
            "latest_files": (
                page_obj.object_list
                if (current_repo_cat and resource_view == "repository")
                else latest_files_qs
            ),
            "recent_files": recent_files,
        },
    )


@login_required
def project_files(request, pk):
    """Simple shortcut view redirecting queries to the filtered document list page."""
    return redirect(f"/files/?project={pk}")
