from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User
from ..models import Project, ProjectModule, ModuleMember, Task, ModuleForumPost
from notifications.models import Notification
from ..forms import ProjectModuleForm, ModuleForumPostForm
from ..decorators import manager_or_admin_required
from ..services.notification_service import NotificationService


@login_required
def module_list(request, pk):
    project = get_object_or_404(Project, pk=pk)

    # Allow access to all project members, managers, incharge, and admins
    is_project_member = (
        request.user.is_admin
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    )

    if not is_project_member:
        messages.error(request, "You do not have access to the modules in this project.")
        return redirect("tasks:project_list")

    # Editors: admin, project incharge, project managers
    is_editor = (
        request.user.is_admin
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    )

    # All editors see all modules; regular members see all modules too (read-only)
    modules = project.modules.all()

    return render(
        request,
        "modules/module_list.html",
        {"project": project, "modules": modules, "is_editor": is_editor},
    )


@login_required
@manager_or_admin_required
def module_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    # Project Managers allowed
    form = ProjectModuleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        module = form.save(commit=False)
        module.project = project
        module.save()
        messages.success(request, f'Module "{module.name}" created.')
        return redirect("tasks:module_list", pk=project.pk)
    return render(
        request,
        "modules/module_form.html",  # Updated path
        {"form": form, "project": project, "title": "Create Module"},
    )


@login_required
def module_detail(request, pk):
    module = get_object_or_404(ProjectModule, pk=pk)
    project = module.project

    # Allow access to all project members, managers, incharge, and admins
    is_project_member = (
        request.user.is_admin
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    )

    if not is_project_member:
        messages.error(request, "You do not have access to this module.")
        return redirect("tasks:project_detail", pk=project.pk)

    # Editors: admin, project incharge, or project manager
    is_editor = (
        request.user.is_admin
        or project.managers.filter(pk=request.user.pk).exists()
        or project.project_incharge == request.user
    )

    members, tasks, kbs, forum_posts = (
        module.members.all(),
        module.tasks.filter(is_in_trash=False),
        module.kb_notes.all(),
        module.forum_posts.filter(parent__isnull=True).select_related("author"),
    )
    requirements = module.requirements.filter(is_in_trash=False)
    forum_form = ModuleForumPostForm()

    if request.method == "POST":
        forum_form = ModuleForumPostForm(request.POST, request.FILES)
        if forum_form.is_valid():
            post = forum_form.save(commit=False)
            post.author, post.module = request.user, module
            parent_id = request.POST.get("parent_id")
            if parent_id:
                try:
                    post.parent = ModuleForumPost.objects.get(pk=parent_id)
                except ModuleForumPost.DoesNotExist:
                    pass
            post.save()

            module_member_users = [
                m.user for m in module.members.all() if m.user != request.user
            ]
            for pm in project.managers.all():
                if pm not in module_member_users:
                    module_member_users.append(pm)

            for member_user in module_member_users:
                NotificationService.create_notification(
                    member_user,
                    request.user,
                    "project_update",
                    f"New post in module: {module.name}",
                    f'{request.user.display_name} posted in the forum of module "{module.name}".',
                    project=project,
                )

            messages.success(request, "Forum post added.")
            return redirect("tasks:module_detail", pk=module.pk)

    return render(
        request,
        "modules/module_detail.html",
        {
            "module": module,
            "project": project,
            "members": members,
            "tasks": tasks,
            "requirements": requirements,
            "kbs": kbs,
            "forum_posts": forum_posts,
            "forum_form": forum_form,
            "is_editor": is_editor,
        },
    )


@login_required
@manager_or_admin_required
def module_edit(request, pk):
    module = get_object_or_404(ProjectModule, pk=pk)
    if False: # request.user.is_project_manager and not request.user.is_admin:
        messages.error(request, "Project Managers can only add or edit requirements.")
        return redirect("tasks:project_detail", pk=module.project.pk)
    form = ProjectModuleForm(request.POST or None, instance=module)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Module "{module.name}" updated.')
        return redirect("tasks:module_detail", pk=module.pk)
    return render(
        request,
        "modules/module_form.html",  # Updated path
        {
            "form": form,
            "project": module.project,
            "title": "Edit Module",
            "module": module,
        },
    )


@login_required
@manager_or_admin_required
def module_delete(request, pk):
    module = get_object_or_404(ProjectModule, pk=pk)
    if False: # request.user.is_project_manager and not request.user.is_admin:
        messages.error(request, "Project Managers can only add or edit requirements.")
        return redirect("tasks:project_detail", pk=module.project.pk)
    project = module.project
    if request.method == "POST":
        module.delete()
        messages.success(request, "Module deleted.")
        return redirect("tasks:module_list", pk=project.pk)
    return render(
        request,
        "projects/confirm_delete.html",  # Updated path
        {"obj": module, "obj_type": "Module"},
    )


@login_required
@manager_or_admin_required
def module_members(request, pk):
    module = get_object_or_404(ProjectModule, pk=pk)
    if False: # request.user.is_project_manager and not request.user.is_admin:
        messages.error(request, "Project Managers can only add or edit requirements.")
        return redirect("tasks:project_detail", pk=module.project.pk)
    project = module.project
    current_members = module.members.all()
    current_member_pks = list(current_members.values_list("user__pk", flat=True))

    # Only show project members/managers who are not yet in this module
    project_user_pks = list(project.members.values_list("pk", flat=True)) + \
                       list(project.managers.values_list("pk", flat=True))
    all_users = User.objects.filter(
        pk__in=project_user_pks, is_active=True
    ).exclude(pk__in=current_member_pks).order_by("first_name", "username")

    if request.method == "POST":
        action, user_id, role = (
            request.POST.get("action"),
            request.POST.get("user_id"),
            request.POST.get("role", "developer"),
        )
        if action and user_id:
            target = get_object_or_404(User, pk=user_id)
            if action == "add":
                ModuleMember.objects.get_or_create(
                    module=module, user=target, defaults={"role": role}
                )
                if (
                    not project.members.filter(pk=target.pk).exists()
                    and not project.managers.filter(pk=target.pk).exists()
                ):
                    project.members.add(target)
                NotificationService.create_notification(
                    target,
                    request.user,
                    "project_update",
                    f"Added to module: {module.name}",
                    f'{request.user.display_name} added you to the module "{module.name}".',
                    project=project,
                )
                messages.success(request, f"{target.display_name} added to the module.")
            elif action == "remove":
                ModuleMember.objects.filter(module=module, user=target).delete()
                messages.success(
                    request, f"{target.display_name} removed from the module."
                )
        return redirect("tasks:module_members", pk=pk)

    return render(
        request,
        "modules/module_members.html",  # Updated path
        {
            "module": module,
            "project": project,
            "all_users": all_users,
            "current_members": current_members,
        },
    )
