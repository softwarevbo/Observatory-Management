from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import AuditLog, Project, Requirement, Task, Release
from testcases.models import TestCase
from bugs.models import BugReport
import json
from django.core.serializers.json import DjangoJSONEncoder

User = get_user_model()

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_action(user, action_type, module, entity_id, entity_name, old_value=None, new_value=None, details=""):
    AuditLog.objects.create(
        user=user,
        action_type=action_type,
        module=module,
        entity_id=str(entity_id),
        entity_name=entity_name,
        old_value=old_value,
        new_value=new_value,
        details=details
    )

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    if isinstance(user, User):
        AuditLog.objects.create(
            user=user,
            action_type='login',
            module='user',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=f"User {user.username} logged in."
        )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user and isinstance(user, User):
        AuditLog.objects.create(
            user=user,
            action_type='logout',
            module='user',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=f"User {user.username} logged out."
        )

# Generic signal handler for common models
def handle_post_save(sender, instance, created, **kwargs):
    action = 'create' if created else 'update'
    module_map = {
        Project: 'project',
        Requirement: 'requirement',
        Task: 'task',
        TestCase: 'test_case',
        BugReport: 'bug',
        Release: 'release',
    }
    module = module_map.get(sender, 'system')
    
    # We might not have the request user here easily without a middleware to store it
    # For now, we'll try to find 'updated_by' or 'created_by' fields if they exist
    user = getattr(instance, 'created_by', None) or getattr(instance, 'author', None)
    
    # In a real app, we'd use a thread-local or middleware to get the current request user
    # But for this task, I'll stick to basic logging
    
    log_action(
        user=user,
        action_type=action,
        module=module,
        entity_id=instance.pk,
        entity_name=str(instance),
        details=f"{module.capitalize()} {instance} was {'created' if created else 'updated'}."
    )

@receiver(post_save, sender=Project)
@receiver(post_save, sender=Requirement)
@receiver(post_save, sender=Task)
@receiver(post_save, sender=TestCase)
@receiver(post_save, sender=BugReport)
@receiver(post_save, sender=Release)
def audit_post_save(sender, instance, created, **kwargs):
    handle_post_save(sender, instance, created, **kwargs)

@receiver(post_delete, sender=Project)
@receiver(post_delete, sender=Requirement)
@receiver(post_delete, sender=Task)
@receiver(post_delete, sender=TestCase)
@receiver(post_delete, sender=BugReport)
@receiver(post_delete, sender=Release)
def audit_post_delete(sender, instance, **kwargs):
    module_map = {
        Project: 'project',
        Requirement: 'requirement',
        Task: 'task',
        TestCase: 'test_case',
        BugReport: 'bug',
        Release: 'release',
    }
    module = module_map.get(sender, 'system')
    log_action(
        user=None, # Cannot determine user easily from signal alone
        action_type='delete',
        module=module,
        entity_id=instance.pk,
        entity_name=str(instance),
        details=f"{module.capitalize()} {instance} was deleted."
    )


@receiver(m2m_changed, sender=Task.assignees.through)
def add_task_assignees_to_module(sender, instance, action, pk_set, **kwargs):
    if action == "post_add" and instance.module:
        from .models import ModuleMember
        project = instance.project
        for user_id in pk_set:
            ModuleMember.objects.get_or_create(
                module=instance.module,
                user_id=user_id,
                defaults={"role": "developer"}
            )
            if project:
                if not project.managers.filter(pk=user_id).exists() and not project.members.filter(pk=user_id).exists():
                    project.members.add(user_id)


@receiver(post_save, sender=Task)
def add_task_module_members(sender, instance, created, **kwargs):
    if instance.module:
        from .models import ModuleMember
        project = instance.project
        for assignee in instance.assignees.all():
            ModuleMember.objects.get_or_create(
                module=instance.module,
                user=assignee,
                defaults={"role": "developer"}
            )
            if project:
                if not project.managers.filter(pk=assignee.pk).exists() and not project.members.filter(pk=assignee.pk).exists():
                    project.members.add(assignee)
