from django.db.models import Q
from .models import SystemSettings
from notifications.models import Notification
from notes.models import KnowledgeBaseNote


def system_settings(request):
    try:
        settings = SystemSettings.get_settings()
        return {"sys_settings": settings}
    except Exception:
        return {}


from django.contrib.auth import get_user_model

User = get_user_model()


def notifications_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(
            recipient_id=request.user.id, is_read=False
        ).count()
        return {"unread_count": count}
    return {}


def notes_count(request):
    if request.user.is_authenticated:
        if request.user.is_admin:
            count = KnowledgeBaseNote.objects.count()
        else:
            count = (
                KnowledgeBaseNote.objects.filter(
                    Q(project__managers__id=request.user.id)
                    | Q(project__members__id=request.user.id)
                    | Q(access_rights__user_id=request.user.id, access_rights__can_view=True)
                )
                .distinct()
                .count()
            )
        return {"notes_count": count}
    return {}


def sidebar_projects(request):
    from .models import Project

    if request.user.is_authenticated:
        if request.user.is_admin:
            projects = Project.objects.all()
        else:
            projects = Project.objects.filter(
                Q(managers__id=request.user.id) | Q(members__id=request.user.id) | Q(project_incharge__id=request.user.id)
            ).distinct()

        projects = projects.prefetch_related(
            "kb_notes", "bug_reports", "files", "files__category"
        )
        return {"sidebar_projects": projects, "global_projects": projects}
    return {}
