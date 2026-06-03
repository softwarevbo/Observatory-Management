import os
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Repository, RepoActivityLog

User = get_user_model()

class ResourceHubTests(TestCase):
    def setUp(self):
        import subprocess
        subprocess.run(['git', 'config', '--global', 'safe.directory', '*'])
        
        self.client = Client()
        # Create test users
        self.owner = User.objects.create_user(username='owner', password='password123', email='owner@example.com')
        self.other_user = User.objects.create_user(username='other', password='password123', email='other@example.com')
        
        # Create repositories
        self.public_repo = Repository.objects.create(
            name="Public Repo",
            owner=self.owner,
            is_private=False,
            description="A public repository"
        )
        self.private_repo = Repository.objects.create(
            name="Private Repo",
            owner=self.owner,
            is_private=True,
            description="A private repository"
        )

    def tearDown(self):
        import shutil
        for repo in [self.public_repo, self.private_repo]:
            if os.path.exists(repo.git_dir):
                try:
                    shutil.rmtree(repo.git_dir)
                except Exception:
                    pass

    def test_repository_slug_auto_generation(self):
        """Verify that slug is auto-generated based on the repository name."""
        self.assertEqual(self.public_repo.slug, "public-repo")
        self.assertEqual(self.private_repo.slug, "private-repo")

    def test_repo_directory_creation_path(self):
        """Verify that git_dir returns the correct directory path."""
        self.assertTrue(self.public_repo.git_dir.endswith("git_repositories/public-repo.git"))

    def test_repo_list_anonymous_redirect(self):
        """Verify that non-logged-in users are redirected to login."""
        response = self.client.get(reverse('resource_hub:repo_list'))
        self.assertEqual(response.status_code, 302) # Redirect to login

    def test_repo_list_authenticated_visibility(self):
        """Verify that public and private repository visibility rules are enforced in listing."""
        # Log in as other_user (not the owner)
        self.client.login(username='other', password='password123')
        
        response = self.client.get(reverse('resource_hub:repo_list'))
        self.assertEqual(response.status_code, 200)
        
        repos = response.context['repos']
        # The other user should see the public repo, but NOT the private repo
        self.assertIn(self.public_repo, repos)
        self.assertNotIn(self.private_repo, repos)

    def test_repo_list_owner_visibility(self):
        """Verify that the owner sees both public and private repositories."""
        self.client.login(username='owner', password='password123')
        
        response = self.client.get(reverse('resource_hub:repo_list'))
        self.assertEqual(response.status_code, 200)
        
        repos = response.context['repos']
        self.assertIn(self.public_repo, repos)
        self.assertIn(self.private_repo, repos)

    def test_write_permission_on_public_repo(self):
        """Verify that general authenticated users do NOT have write permission on public repo unless added as collaborator."""
        from .views import check_repo_access
        
        class DummyRequest:
            def __init__(self, user):
                self.user = user
                
        request = DummyRequest(self.other_user)
        # General authenticated user should NOT have write permission on public repo
        has_access, is_owner = check_repo_access(request, self.public_repo, require_write=True)
        self.assertFalse(has_access)
        self.assertFalse(is_owner)
        
        # Adding as collaborator should grant write permission
        self.public_repo.collaborators.add(self.other_user)
        has_access, is_owner = check_repo_access(request, self.public_repo, require_write=True)
        self.assertTrue(has_access)

    def test_write_permission_on_private_repo(self):
        """Verify that general authenticated users do NOT have write permission on private repo."""
        from .views import check_repo_access
        
        class DummyRequest:
            def __init__(self, user):
                self.user = user
                
        request = DummyRequest(self.other_user)
        has_access, is_owner = check_repo_access(request, self.private_repo, require_write=True)
        self.assertFalse(has_access)
        self.assertFalse(is_owner)

    def test_repo_file_view_rendering(self):
        """Verify that the file viewer page renders correctly without template errors."""
        import tempfile
        import subprocess
        
        repo_dir = self.public_repo.git_dir
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize empty git repo and link origin
            subprocess.run(['git', '-c', 'safe.directory=*', 'init', temp_dir], check=True)
            subprocess.run(['git', '-c', 'safe.directory=*', '-C', temp_dir, 'remote', 'add', 'origin', repo_dir], check=True)
            
            # Write a test file
            test_file_path = os.path.join(temp_dir, 'hello.txt')
            with open(test_file_path, 'w') as f:
                f.write("Line 1\nLine 2\nLine 3\n")
                
            # Configure git user and commit
            subprocess.run(['git', '-c', 'safe.directory=*', '-C', temp_dir, 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-c', 'safe.directory=*', '-C', temp_dir, 'config', 'user.email', 'test@test.com'], check=True)
            subprocess.run(['git', '-c', 'safe.directory=*', '-C', temp_dir, 'add', 'hello.txt'], check=True)
            subprocess.run(['git', '-c', 'safe.directory=*', '-C', temp_dir, 'commit', '-m', 'Add hello.txt'], check=True)
            proc = subprocess.run(['git', '-c', 'safe.directory=*', '-C', temp_dir, 'push', '-u', 'origin', 'master'], capture_output=True, text=True)
            if proc.returncode != 0:
                print("PUSH STDOUT:", proc.stdout)
                print("PUSH STDERR:", proc.stderr)
                raise Exception("Git push failed")
            subprocess.run(['git', '-c', 'safe.directory=*', '-C', repo_dir, 'symbolic-ref', 'HEAD', 'refs/heads/master'], check=True)
            
        self.client.login(username='owner', password='password123')
        url = reverse('resource_hub:repo_file_view', kwargs={'slug': self.public_repo.slug, 'ref': 'master', 'path': 'hello.txt'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['line_count'], 3)
        self.assertContains(response, "hello.txt")

    def test_repo_user_guide_rendering(self):
        """Verify that the user guide renders correctly and contains setup details."""
        self.client.login(username='owner', password='password123')
        url = reverse('resource_hub:repo_user_guide', kwargs={'slug': self.public_repo.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resource Hub Integration Guide")
        self.assertContains(response, "git clone")

    def test_repo_logs_owner_only(self):
        """Verify that only the repo creator/owner can access logs."""
        # Check non-owner gets 403
        self.client.login(username='other', password='password123')
        url = reverse('resource_hub:repo_logs', kwargs={'slug': self.public_repo.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # Check owner gets 200
        self.client.login(username='owner', password='password123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Repository Activity Logs")

    def test_repo_download_zip(self):
        """Verify that the repository zip archive download is fully functional."""
        self.test_repo_file_view_rendering() # Set up master branch and hello.txt
        
        self.client.login(username='owner', password='password123')
        url = reverse('resource_hub:repo_download_zip', kwargs={'slug': self.public_repo.slug, 'ref': 'master'})
        response = self.client.get(url, HTTP_X_FORWARDED_FOR='192.168.99.1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        
        # Verify activity log contains original IP
        log_entry = RepoActivityLog.objects.filter(repository=self.public_repo, action='download_zip').first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.ip_address, '192.168.99.1')

    def test_repo_create_file(self):
        """Verify web-based repository file creation and commit workflow."""
        self.test_repo_file_view_rendering() # Initialize repo to non-empty
        
        self.client.login(username='owner', password='password123')
        
        # Verify page renders
        get_url = reverse('resource_hub:repo_create_file', kwargs={'slug': self.public_repo.slug})
        response = self.client.get(get_url)
        self.assertEqual(response.status_code, 200)
        
        # Perform online file creation post
        post_data = {
            'file_path': 'docs/web-created.txt',
            'file_content': 'Created directly from Web interface!',
            'commit_message': 'Auto-created from web interface test',
            'branch': 'master'
        }
        post_response = self.client.post(get_url, post_data, HTTP_X_FORWARDED_FOR='10.20.30.40')
        self.assertEqual(post_response.status_code, 302) # Redirects back to directory/code page
        
        # Verify file is created in repository git tree
        import subprocess
        ls_proc = subprocess.run([
            'git', '-C', self.public_repo.git_dir, 'ls-tree', '-r', '--name-only', 'master'
        ], capture_output=True, text=True)
        self.assertIn('docs/web-created.txt', ls_proc.stdout)
        
        # Verify IP address and action are correctly logged
        log_entry = RepoActivityLog.objects.filter(repository=self.public_repo, action='create_file').first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.ip_address, '10.20.30.40')

    def test_repo_collaborators_permissions(self):
        """Verify that only authorized collaborators can write/push to a repo."""
        from .views import check_repo_access
        
        # public repo write: should be False for general other_user
        class DummyRequest:
            def __init__(self, user):
                self.user = user
                
        request = DummyRequest(self.other_user)
        has_access, is_owner = check_repo_access(request, self.public_repo, require_write=True)
        self.assertFalse(has_access)
        
        # Add other_user as collaborator
        self.public_repo.collaborators.add(self.other_user)
        
        # Now has_access should be True
        has_access, is_owner = check_repo_access(request, self.public_repo, require_write=True)
        self.assertTrue(has_access)

    def test_repo_settings_collaborator_management(self):
        """Verify adding and removing collaborators via the invite-accept flow."""
        self.client.login(username='owner', password='password123')
        settings_url = reverse('resource_hub:repo_settings', kwargs={'slug': self.public_repo.slug})

        # Step 1: Owner sends invitation to other_user
        post_data = {
            'action': 'add_collaborator',
            'user_id': self.other_user.pk
        }
        response = self.client.post(settings_url, post_data)
        self.assertEqual(response.status_code, 302)

        # Step 2: Verify invitation was created (not direct collaborator yet)
        from .models import RepoInvitation
        invite = RepoInvitation.objects.filter(
            repository=self.public_repo,
            invitee=self.other_user,
            is_accepted=False
        ).first()
        self.assertIsNotNone(invite, "Expected a RepoInvitation to be created")
        self.assertFalse(self.public_repo.collaborators.filter(pk=self.other_user.pk).exists(),
                         "User should NOT be a collaborator before accepting the invite")

        # Step 3: other_user accepts the invitation
        self.client.login(username='other', password='password123')
        accept_url = reverse('resource_hub:repo_accept_invite', kwargs={'invite_id': invite.pk})
        response = self.client.get(accept_url)
        self.assertEqual(response.status_code, 302)

        # Step 4: Verify they are now a collaborator
        self.assertTrue(self.public_repo.collaborators.filter(pk=self.other_user.pk).exists(),
                        "User should be a collaborator after accepting the invite")

        # Step 5: Owner removes them via settings
        self.client.login(username='owner', password='password123')
        remove_data = {
            'action': 'remove_collaborator',
            'user_id': self.other_user.pk
        }
        response = self.client.post(settings_url, remove_data)
        self.assertEqual(response.status_code, 302)

        # Step 6: Verify they are no longer a collaborator
        self.assertFalse(self.public_repo.collaborators.filter(pk=self.other_user.pk).exists(),
                         "User should NOT be a collaborator after removal")

