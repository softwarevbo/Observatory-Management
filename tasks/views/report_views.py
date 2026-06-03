from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.timezone import now
import io

from ..models import Project, Task, AuditLog
from testcases.models import TestCase
from ..services.report_engine import ReportEngine
from ..utils.query_utils import get_visible_tasks_qs


@login_required
def reports_view(request):
    if request.user.is_admin:
        messages.info(request, "Reports are not available in admin mode.")
        return redirect("tasks:project_list")

    if request.user.is_project_manager:
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(managers=request.user) | Q(members=request.user)
        ).distinct()
    tasks = get_visible_tasks_qs(
        request.user, Task.objects.filter(project__in=projects)
    )

    task_by_status = {s: tasks.filter(status=s).count() for s, _ in Task.STATUS_CHOICES}
    task_by_priority = {
        p: tasks.filter(priority=p).count() for p, _ in Task.PRIORITY_CHOICES
    }
    proj_by_status = {
        s: projects.filter(status=s).count() for s, _ in Project.STATUS_CHOICES
    }
    proj_by_module = {
        m: projects.filter(module=m).count() for m, _ in Project.MODULE_CHOICES
    }
    overdue_tasks = [
        t
        for t in tasks.select_related("project").prefetch_related("assignees")
        if t.is_overdue
    ]
    
    completed_tasks = tasks.filter(status="done").count()
    active_projects = projects.filter(status="active").count()

    # Team workload calculation based on modules
    team_workload = []
    from ..models import ProjectModule
    visible_modules = ProjectModule.objects.filter(project__in=projects).distinct()
    for m in visible_modules:
        open_tasks_count = tasks.filter(module=m).exclude(status="done").count()
        member_count = m.members.count()
        if open_tasks_count > 0 or member_count > 0:
            team_workload.append({
                "team": f"{m.project.name}: {m.name}",
                "open_tasks": open_tasks_count,
                "members": member_count
            })

    return render(
        request,
        "reports/reports.html",  # Updated path
        {
            "task_by_status": task_by_status,
            "task_by_priority": task_by_priority,
            "proj_by_status": proj_by_status,
            "proj_by_module": proj_by_module,
            "overdue_tasks": overdue_tasks,
            "projects": projects,
            "completed_tasks": completed_tasks,
            "active_projects": active_projects,
            "team_workload": team_workload,
        },
    )


@login_required
def report_center(request):
    if request.user.is_project_manager:
        projects = Project.objects.all()
    else:
        projects = Project.objects.filter(
            Q(managers=request.user) | Q(members=request.user)
        ).distinct()

    context = {
        "projects": projects,
        "template_choices": [
            ("srs", "Software Requirement Specification (SRS)"),
            ("brd", "Business Requirement Document (BRD)"),
            ("frd", "Functional Requirement Document (FRD)"),
        ],
        "format_choices": [
            ("pdf", "PDF Document"),
            ("docx", "MS Word (DOCX)"),
            ("xlsx", "MS Excel (XLSX)"),
            ("md", "Markdown Document (MD)"),
        ],
    }
    return render(request, "reports/report_center.html", context)

@login_required
def project_report_center(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not (
        request.user.is_admin
        or request.user.is_project_manager
        or project.managers.filter(pk=request.user.pk).exists()
        or project.members.filter(pk=request.user.pk).exists()
    ):
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")

    context = {
        "project": project,
        "template_choices": [
            ("srs", "Software Requirement Specification (SRS)"),
            ("brd", "Business Requirement Document (BRD)"),
            ("frd", "Functional Requirement Document (FRD)"),
        ],
        "format_choices": [
            ("pdf", "PDF Document"),
            ("docx", "MS Word (DOCX)"),
            ("xlsx", "MS Excel (XLSX)"),
            ("md", "Markdown Document (MD)"),
        ],
        "report_logs": AuditLog.objects.filter(module="project", action_type="download", entity_id=str(project.pk)).order_by('-timestamp')[:5]
    }
    return render(request, "reports/project_report_center.html", context)


@login_required
def master_report(request, pk):
    """Generate a comprehensive master report for a project."""
    project = get_object_or_404(Project, pk=pk)
    
    if not (request.user.is_admin or request.user.is_project_manager or
            project.managers.filter(pk=request.user.pk).exists() or
            project.members.filter(pk=request.user.pk).exists()):
        messages.error(request, "Access denied.")
        return redirect("tasks:project_list")
        
    format_type = request.GET.get("format", "pdf")
    template_type = request.GET.get("template", "master")
    
    # Audit Logging
    AuditLog.objects.create(
        user=request.user,
        action_type="download",
        module="project",
        entity_id=str(project.pk),
        entity_name=project.name,
        details=format_type
    )

    if format_type == "docx":
        doc_bytes = ReportEngine.generate_master_report(project, format='docx')
        response = HttpResponse(doc_bytes, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="{project.project_id}_Master_Report.docx"'
        return response
    elif format_type == "xlsx":
        xls_bytes = ReportEngine.generate_master_report(project, format='xlsx')
        response = HttpResponse(xls_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{project.project_id}_Master_Report.xlsx"'
        return response
    elif format_type == "md":
        md_bytes = ReportEngine.generate_master_report(project, format='md')
        response = HttpResponse(md_bytes, content_type='text/markdown')
        response['Content-Disposition'] = f'attachment; filename="{project.project_id}_Master_Report.md"'
        return response
    else:
        # PDF or HTML
        pdf_bytes = ReportEngine.generate_master_report(project, format=format_type)
        if format_type == "html":
            return HttpResponse(pdf_bytes)
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{project.project_id}_Master_Report.pdf"'
        return response
