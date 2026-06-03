import os
import shutil
from django.db import models
from django.conf import settings
from django.utils.text import slugify

class Repository(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Unique name for the repository.")
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text="Slug used for URL and repository directory name.")
    description = models.TextField(blank=True, default='', help_text="Optional description of the repository.")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='repositories',
        help_text="User who owns this repository."
    )
    is_private = models.BooleanField(default=False, help_text="If checked, only the owner, collaborators, and admins can access this repository.")
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='collaborating_repositories',
        help_text="Users who are collaborators and have write access to this repository."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Repositories"
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        
        # Initialize bare repository if it does not exist
        git_dir = self.git_dir
        if not os.path.exists(os.path.join(git_dir, 'HEAD')):
            import subprocess
            os.makedirs(git_dir, exist_ok=True)
            # Add safe.directory configuration to avoid ownership restrictions during initialization
            subprocess.run(['git', '-c', 'safe.directory=*', 'init', '--bare', git_dir], check=True)
            subprocess.run([
                'git', '-c', 'safe.directory=*', 'config', '-f', os.path.join(git_dir, 'config'), 'http.receivepack', 'true'
            ], check=True)

    @property
    def git_dir(self):
        return os.path.join(settings.MEDIA_ROOT, 'git_repositories', f"{self.slug}.git")

    def delete(self, *args, **kwargs):
        # Clean up the bare repository directory when deleted
        repo_path = self.git_dir
        if os.path.exists(repo_path):
            try:
                shutil.rmtree(repo_path)
            except Exception:
                pass
        super().delete(*args, **kwargs)


class RepoActivityLog(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='activity_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50) # 'clone/pull', 'push', 'web_upload', etc.
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} on {self.repository.name} at {self.created_at}"


class RepoInvitation(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='invitations')
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='repo_invitations')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_repo_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('repository', 'invitee')

    def __str__(self):
        return f"Invite for {self.invitee.username} to {self.repository.name}"
