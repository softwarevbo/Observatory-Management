from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.conf import settings
from .models import UserPresence, ChatRoom
from tasks.models import Project

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_presence(sender, instance, created, **kwargs):
    if created:
        UserPresence.objects.get_or_create(user=instance)

@receiver(post_save, sender=Project)
def create_project_chat_room(sender, instance, created, **kwargs):
    if created:
        room = ChatRoom.objects.create(
            name=f"Project: {instance.name}",
            room_type='project',
            project=instance
        )
        # Add creator as participant
        if instance.created_by:
            room.participants.add(instance.created_by)
        # Add managers
        for manager in instance.managers.all():
            room.participants.add(manager)

@receiver(m2m_changed, sender=Project.members.through)
def update_project_chat_participants(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        room = ChatRoom.objects.filter(project=instance).first()
        if room:
            for pk in pk_set:
                room.participants.add(pk)
