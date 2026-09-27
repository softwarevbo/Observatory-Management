"""
tasks/views/git_views.py

Views for Git integration:
  - git_settings          : PM-only config form (GET/POST)
  - git_test_connection   : AJAX endpoint to test SSH/HTTPS connectivity
  - git_push_release      : Performs git add+commit+push for selected release files
  - git_push_log          : History of pushes for a project
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import Project, Release, ProjectGitConfig, ProjectGitPushLog
from ..decorators import manager_or_admin_required


# ─── Git Settings (Project Manager UI) ────────────────────────────────────────

@login_required
@manager_or_admin_required
def git_settings(request, pk):
    """Show and save Git configuration for a project."""
    project = get_object_or_404(Project, pk=pk)

    # Access control: only managers / admins
    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "Only project managers can configure Git settings.")
        return redirect("tasks:project_detail", pk=pk)

    git_config, created = ProjectGitConfig.objects.get_or_create(
        project=project,
        defaults={"created_by": request.user},
    )

    push_logs = ProjectGitPushLog.objects.filter(project=project).select_related(
        "triggered_by", "release"
    )[:20]

    if request.method == "POST":
        # Basic fields
        git_config.remote_url = request.POST.get("remote_url", "").strip()
        git_config.branch = request.POST.get("branch", "main").strip() or "main"
        git_config.auth_method = request.POST.get("auth_method", "ssh_key")
        git_config.git_username = request.POST.get("git_username", "").strip()
        git_config.git_email = request.POST.get("git_email", "").strip()
        git_config.https_username = request.POST.get("https_username", "").strip()
        git_config.release_dir = request.POST.get("release_dir", "").strip()
        git_config.is_active = request.POST.get("is_active") == "on"

        # Secrets — only update if the user sent a non-empty value
        ssh_key_input = request.POST.get("ssh_private_key", "").strip()
        if ssh_key_input:
            git_config.set_ssh_private_key(ssh_key_input)

        https_token_input = request.POST.get("https_token", "").strip()
        if https_token_input:
            git_config.set_https_token(https_token_input)

        git_config.save()
        messages.success(request, "Git configuration saved successfully.")
        return redirect("tasks:git_settings", pk=pk)

    context = {
        "project": project,
        "git_config": git_config,
        "push_logs": push_logs,
        "title": f"Git Settings — {project.name}",
        # Mask the stored key/token so the user can see "configured" status
        "has_ssh_key": bool(git_config._ssh_private_key_enc),
        "has_https_token": bool(git_config._https_token_enc),
    }
    return render(request, "git/git_settings.html", context)


# ─── Test Connection (AJAX) ────────────────────────────────────────────────────

@login_required
@require_POST
def git_test_connection(request, pk):
    """AJAX: test connectivity to the configured remote."""
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
    ):
        return JsonResponse({"ok": False, "message": "Permission denied."}, status=403)

    try:
        git_config = project.git_config
    except ProjectGitConfig.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Git is not configured for this project."})

    from ..services.git_service import GitService
    result = GitService.test_connection(git_config)
    return JsonResponse(result)


# ─── Git Push (Release files) ──────────────────────────────────────────────────

@login_required
@require_POST
def git_push_release(request, pk):
    """
    Perform git add + commit + push for selected release files.

    POST params:
        release_id     : int
        file_ids[]     : list of ReleaseFile PKs
        commit_message : str
    """
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
    ):
        return JsonResponse({"ok": False, "message": "Permission denied."}, status=403)

    # Fetch git config
    try:
        git_config = project.git_config
    except ProjectGitConfig.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "message": "Git is not configured for this project. Visit Project Settings → Git.",
        })

    if not git_config.is_active:
        return JsonResponse({"ok": False, "message": "Git integration is disabled for this project."})

    release_id = request.POST.get("release_id")
    file_ids = request.POST.getlist("file_ids[]") or request.POST.getlist("file_ids")
    commit_message = request.POST.get("commit_message", "").strip()

    if not release_id:
        return JsonResponse({"ok": False, "message": "No release specified."})
    if not file_ids:
        return JsonResponse({"ok": False, "message": "No files selected."})
    if not commit_message:
        return JsonResponse({"ok": False, "message": "Commit message is mandatory."})

    release = get_object_or_404(Release, pk=release_id, project=project)

    from ..services.git_service import GitService
    result = GitService.push_release_files(
        git_config=git_config,
        release=release,
        release_file_ids=[int(fid) for fid in file_ids],
        commit_message=commit_message,
        triggered_by=request.user,
    )
    return JsonResponse(result)


# ─── Push Log (project-level audit) ───────────────────────────────────────────

@login_required
def git_push_log(request, pk):
    """Show git push history for a project."""
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "Permission denied.")
        return redirect("tasks:project_detail", pk=project.pk)

    logs = ProjectGitPushLog.objects.filter(project=project).select_related(
        "triggered_by", "release"
    )
    return render(request, "git/git_push_log.html", {
        "project": project,
        "logs": logs,
        "title": f"Git Push History — {project.name}",
    })


@login_required
@manager_or_admin_required
def git_generate_ssh_key(request, pk):
    """AJAX endpoint to auto-generate a new RSA SSH Keypair for the project."""
    project = get_object_or_404(Project, pk=pk)
    
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    try:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Private key in PEM (OpenSSH format)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Public key in OpenSSH format
        public_ssh = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')
        
        return JsonResponse({
            "ok": True,
            "private_key": private_pem,
            "public_key": public_ssh
        })
    except Exception as e:
        return JsonResponse({
            "ok": False,
            "message": f"Failed to generate SSH key: {str(e)}"
        })


@login_required
@require_POST
def git_diff_check(request, pk):
    """
    Perform a dry-run git diff showing changes of files before push.
    """
    project = get_object_or_404(Project, pk=pk)

    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
    ):
        return JsonResponse({"ok": False, "message": "Permission denied."}, status=403)

    try:
        git_config = project.git_config
    except ProjectGitConfig.DoesNotExist:
        return JsonResponse({"ok": False, "message": "Git is not configured for this project."})

    if not git_config.is_active:
        return JsonResponse({"ok": False, "message": "Git integration is disabled."})

    release_id = request.POST.get("release_id")
    file_ids = request.POST.getlist("file_ids[]") or request.POST.getlist("file_ids")

    if not release_id:
        return JsonResponse({"ok": False, "message": "No release specified."})

    release = get_object_or_404(Release, pk=release_id, project=project)

    from ..services.git_service import GitService
    result = GitService.get_release_diff(
        git_config=git_config,
        release=release,
        release_file_ids=[int(fid) for fid in file_ids],
    )
    return JsonResponse(result)
