from django.core.files.base import ContentFile
from files.models import FileCategory, ProjectFile
from ..models import Project
from .notification_service import NotificationService


class ProjectService:
    @staticmethod
    def initialize_project_folders(project, user):
        """
        Creates the default folder structure for a new project.
        """
        # Resources
        res_cat = FileCategory.objects.create(
            name="resources", project=project, created_by=user
        )
        FileCategory.objects.create(
            name="notes", parent=res_cat, project=project, created_by=user
        )
        FileCategory.objects.create(
            name="documents", parent=res_cat, project=project, created_by=user
        )
        FileCategory.objects.create(
            name="assets", parent=res_cat, project=project, created_by=user
        )


        # Releases
        rel_cat = FileCategory.objects.create(
            name="Releases", project=project, created_by=user
        )

        # README
        readme_content = (
            f"# {project.name}\n\n{project.description}\n\nWelcome to your new project."
        )
        readme_file = ProjectFile(
            original_name="README.md",
            project=project,
            uploaded_by=user,
            description="Project README",
            is_public=True,
        )
        readme_file.file.save("README.md", ContentFile(readme_content.encode("utf-8")))
        readme_file.save()

    @staticmethod
    def notify_project_assignment(project, sender):
        """
        Notifies managers and members when they are assigned to a project.
        """
        # Notify project managers
        for pm in project.managers.exclude(pk=sender.pk):
            NotificationService.create_notification(
                pm,
                sender,
                "project_update",
                f"You were assigned as Project Manager: {project.name}",
                f'{sender.display_name} assigned you as the manager of project "{project.name}".',
                project=project,
            )

        # Notify all assigned members
        for member in project.members.all():
            NotificationService.create_notification(
                member,
                sender,
                "project_update",
                f"You were added to project: {project.name}",
                f'{sender.display_name} added you as a member of "{project.name}".',
                project=project,
            )

    @staticmethod
    def handle_deletion_request(project, user, action, reason=""):
        """
        Handles project deletion requests, approvals, and cancellations.
        """
        from django.utils import timezone
        from ..models import ProjectDeletionRequest

        name = project.name
        message = ""

        if action == "request_deletion":
            project.deletion_requested_at = timezone.now()
            if user.is_admin:
                project.deletion_requested_by_admin = True
                project.save()
                message = f'Project "{name}" deletion requested. Waiting for Project Manager approval.'
                for manager in project.managers.all():
                    NotificationService.create_notification(
                        manager,
                        user,
                        "project_update",
                        "Project Deletion Requested",
                        f'Admin {user.display_name} has requested to delete project "{name}". Please approve.',
                        project=project,
                    )
            elif (
                user.is_project_manager and project.managers.filter(pk=user.pk).exists()
            ):
                project.deletion_requested_by_pm = True
                project.save()
                message = (
                    f'Project "{name}" deletion requested. Waiting for Admin approval.'
                )
                from accounts.models import User

                for admin in User.objects.filter(Q(role='admin') | Q(is_superuser=True)):
                    NotificationService.create_notification(
                        admin,
                        user,
                        "project_update",
                        "Project Deletion Requested",
                        f'PM {user.display_name} has requested to delete project "{name}". Please approve.',
                        project=project,
                    )
            
            # Create the actual request object
            ProjectDeletionRequest.objects.create(
                project=project,
                requested_by=user,
                reason=reason if reason else "No reason provided."
            )

        elif action == "cancel_deletion":
            if user.is_admin or (
                user.is_project_manager and project.managers.filter(pk=user.pk).exists()
            ):
                project.deletion_requested_by_admin = False
                project.deletion_requested_by_pm = False
                project.deletion_requested_at = None
                project.save()
                message = f'Deletion request for "{name}" cancelled.'
                
            # Delete pending requests for this project
            ProjectDeletionRequest.objects.filter(project=project, status='pending').delete()

        return message
