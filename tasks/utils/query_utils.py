from django.db.models import Q
from notes.models import KnowledgeBaseNote


def get_visible_tasks_qs(user, tasks_qs):
    # Always filter out items in trash unless in trash view
    tasks_qs = tasks_qs.filter(is_in_trash=False).exclude(linked_bugs__is_in_trash=True)
    
    if user.is_admin:
        return tasks_qs
    if user.is_project_manager:
        return tasks_qs.filter(
            Q(project__managers=user)
            | Q(project__members=user)
            | Q(project__project_incharge=user)
        ).distinct()
    return tasks_qs.filter(
        Q(is_approved=True) | Q(created_by=user)
    ).filter(
        Q(project__managers=user)
        | Q(assignees=user)
        | Q(project__members=user)
        | Q(project__project_incharge=user)
    ).distinct()


def get_visible_notes_qs(user):
    qs = KnowledgeBaseNote.objects.filter(is_in_trash=False)
    if user.is_admin:
        return qs.filter(
            Q(project__isnull=False) | Q(project__isnull=True, author=user)
        ).distinct()
    if user.is_project_manager:
        return qs.filter(
            Q(project__managers=user)
            | Q(project__members=user)
            | Q(project__project_incharge=user)
            | Q(project__isnull=True, author=user)
        ).distinct()
    return qs.filter(
        Q(project__managers=user)
        | Q(project__members=user)
        | Q(project__project_incharge=user)
        | Q(access_rights__user=user, access_rights__can_view=True)
        | Q(project__isnull=True, author=user)
    ).distinct()
