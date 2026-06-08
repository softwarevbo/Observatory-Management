import os
import base64
import logging
import shutil
import tempfile
import subprocess
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseNotFound, HttpResponseForbidden, Http404
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.urls import reverse
from django.utils.text import slugify

from django.db import models
from .models import Repository, RepoActivityLog, RepoInvitation

# --- Helper Functions ---

def get_basic_auth_user(request):
    """
    Authenticate user using HTTP Basic Auth (crucial for git CLI client interactions).
    """
    # Extract the Authorization header containing credentials
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if auth_header and auth_header.startswith('Basic '):
        try:
            # Split off the 'Basic ' prefix and retrieve encoded base64 string
            encoded_credentials = auth_header.split(' ', 1)[1]
            # Decode the base64 string to utf-8 format
            decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
            # Split the credentials into username and password tokens
            username, password = decoded_credentials.split(':', 1)
            # Authenticate user credentials against Django auth backends
            user = authenticate(username=username, password=password)
            if user is not None:
                return user
        except Exception:
            # Silently catch exceptions to fail auth safely
            pass
    return None

def is_repo_empty(repo_dir):
    """
    Check if a bare git repository has any commits in any branch.
    """
    try:
        # Run 'git show-ref' inside bare directory which lists all existing branch/tag refs
        proc = subprocess.run(['git', '-C', repo_dir, 'show-ref'], capture_output=True)
        # If exit status is non-zero, it means no refs exist, meaning the repository is empty
        return proc.returncode != 0
    except Exception:
        return True

def get_default_branch(repo_dir):
    """
    Find default branch (main/master) of a bare repo, fallback to any active branch.
    """
    try:
        # Query symbolic-ref HEAD to find the primary configured branch name
        proc = subprocess.run(['git', '-C', repo_dir, 'symbolic-ref', '--short', 'HEAD'], capture_output=True, text=True, check=True)
        branch = proc.stdout.strip()
        # Verify if this branch actually contains any commits in its revision log
        check = subprocess.run(['git', '-C', repo_dir, 'rev-parse', '--verify', branch], capture_output=True)
        if check.returncode == 0:
            return branch
    except Exception:
        pass

    # If HEAD symbolic-ref fails, fallback to the first branch that actually has commits
    try:
        proc = subprocess.run(['git', '-C', repo_dir, 'branch', '--format=%(refname:short)'], capture_output=True, text=True, check=True)
        branches = [b.strip() for b in proc.stdout.split('\n') if b.strip()]
        if branches:
            return branches[0]
    except Exception:
        pass

    # Default fallback string if no branches exist
    return 'main'

def get_branches(repo_dir):
    """
    List all branches present in a repository.
    """
    try:
        # Query git branch formatting only the short name of refs
        proc = subprocess.run(['git', '-C', repo_dir, 'branch', '--format=%(refname:short)'], capture_output=True, text=True, check=True)
        branches = [b.strip() for b in proc.stdout.split('\n') if b.strip()]
        return branches if branches else ['main']
    except Exception:
        return ['main']

def get_object_type(repo_dir, ref, path):
    """
    Check if a specific ref/path object is a tree (directory) or blob (file).
    """
    try:
        # Build reference format e.g. "main:src/utils.py"
        target = f"{ref}:{path}" if path else ref
        # Run cat-file -t to query type information (tree, blob, commit)
        proc = subprocess.run(['git', '-C', repo_dir, 'cat-file', '-t', target], capture_output=True, text=True, check=True)
        return proc.stdout.strip()
    except Exception:
        return None

def check_repo_access(request, repo, require_write=False):
    """
    Check if the request user has read/write permissions for the target repository.
    Returns (has_access, is_owner_or_admin).
    """
    user = request.user
    
    # Assess role configuration flags
    is_authenticated = user.is_authenticated
    is_admin = is_authenticated and (getattr(user, 'is_admin', False) or user.is_superuser)
    is_owner = is_authenticated and (repo.owner == user)
    is_collaborator = is_authenticated and repo.collaborators.filter(pk=user.pk).exists()

    # Owner & Admin can always do anything
    if is_owner or is_admin:
        return True, True

    if require_write:
        # Strict write permissions: only owner, admin, or collaborator can write/push
        return is_collaborator, False

    # Read operations (pulling from CLI, browsing Web UI)
    if repo.is_private:
        # Private repo: only owner, admin, or collaborator has access
        return is_collaborator, False
    else:
        # Public repo: any logged-in user can access/read
        return is_authenticated, False

def get_client_ip(request):
    """
    Retrieve the client IP address from request headers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR')
    return ip

def get_clone_url(request, repo):
    """
    Generate the HTTP clone URL for the repository.
    """
    # Build complete absolute URL path pointing to git smart HTTP CGI endpoint
    clone_url = request.build_absolute_uri(
        reverse('resource_hub:git_smart_http', kwargs={'slug': repo.slug, 'git_path': 'info/refs'})
    )
    # Strip off trailing path if present
    if clone_url.endswith('/info/refs'):
        clone_url = clone_url[:-10]
    return clone_url


# --- Git Smart HTTP Server Endpoint ---

logger = logging.getLogger(__name__)

def _find_git_http_backend():
    """Locate the git-http-backend CGI executable on this system."""
    candidates = [
        '/usr/lib/git-core/git-http-backend',
        '/usr/libexec/git-core/git-http-backend',
        '/usr/lib/git/git-http-backend',
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    # Fallback: ask the shell
    try:
        result = subprocess.run(['which', 'git-http-backend'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    # Last resort — most common path on Debian/Ubuntu
    return '/usr/lib/git-core/git-http-backend'

_GIT_HTTP_BACKEND = _find_git_http_backend()

@csrf_exempt
def git_smart_http_view(request, slug, git_path):
    """
    CGI wrapper around git-http-backend.
    Supports clone/push/pull operations using Django user authentication.
    """
    # Retrieve repository model
    repo = get_object_or_404(Repository, slug=slug)

    # Verify the bare repository directory actually exists on disk
    if not os.path.isdir(repo.git_dir):
        logger.error("Git repo directory missing: %s", repo.git_dir)
        return HttpResponse(
            f"Repository directory not found. Please contact an administrator.",
            status=500, content_type="text/plain"
        )

    # Detect if request is pushing changes (git-receive-pack service type)
    is_push = (git_path == 'git-receive-pack' or request.GET.get('service') == 'git-receive-pack')

    # Authenticate Basic Auth user if git CLI client is sending authorization headers
    auth_user = get_basic_auth_user(request)
    if auth_user:
        request.user = auth_user

    # Verify write (push) or read (pull/clone) permissions
    has_access, _ = check_repo_access(request, repo, require_write=is_push)
    
    if not has_access:
        # Return HTTP 401 Unauthorized to trigger Git client Basic Auth credentials popup
        response = HttpResponse("Unauthorized", status=401)
        response['WWW-Authenticate'] = 'Basic realm="Git Repository"'
        return response

    # Log actions performed by git CLI clients
    if git_path in ['git-upload-pack', 'git-receive-pack']:
        action_name = 'push' if git_path == 'git-receive-pack' else 'clone/pull'
        username = request.user.username if request.user.is_authenticated else 'Anonymous'
        desc = f"Git client {action_name} performed by user '{username}'"
        try:
            ip = get_client_ip(request)
            RepoActivityLog.objects.create(
                repository=repo,
                user=request.user if request.user.is_authenticated else None,
                action=action_name,
                description=desc,
                ip_address=ip
            )
        except Exception:
            pass

    # Map environment variables required by git-http-backend CGI script
    env = os.environ.copy()
    env['GIT_PROJECT_ROOT'] = os.path.dirname(repo.git_dir)
    env['GIT_HTTP_EXPORT_ALL'] = '1'
    env['PATH_INFO'] = f"/{repo.slug}.git/{git_path}"
    env['QUERY_STRING'] = request.META.get('QUERY_STRING', '')
    env['REQUEST_METHOD'] = request.method
    env['CONTENT_TYPE'] = request.headers.get('Content-Type', '')
    env['CONTENT_LENGTH'] = request.headers.get('Content-Length', '')
    if request.user.is_authenticated:
        env['REMOTE_USER'] = request.user.username

    # CRITICAL: Bypass git safe.directory ownership checks (git ≥ 2.35.2).
    # Without this, git-http-backend returns fatal errors when the Django process
    # user differs from the directory owner.
    env['GIT_CONFIG_COUNT'] = '1'
    env['GIT_CONFIG_KEY_0'] = 'safe.directory'
    env['GIT_CONFIG_VALUE_0'] = '*'

    try:
        # Spawn git-http-backend process
        proc = subprocess.Popen(
            [_GIT_HTTP_BACKEND],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Pipe body payload from request into the subprocess stdin
        input_data = request.body
        stdout_data, stderr_data = proc.communicate(input=input_data, timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        logger.error("git-http-backend timed out for repo=%s path=%s", slug, git_path)
        return HttpResponse("Git operation timed out.", status=504, content_type="text/plain")
    except FileNotFoundError:
        logger.error("git-http-backend not found at: %s", _GIT_HTTP_BACKEND)
        return HttpResponse(
            "Git HTTP backend not installed on server.",
            status=500, content_type="text/plain"
        )
    except Exception as exc:
        logger.exception("git-http-backend process error for repo=%s: %s", slug, exc)
        return HttpResponse(
            "Internal server error during Git operation.",
            status=500, content_type="text/plain"
        )

    # Check for process execution failures
    if proc.returncode != 0:
        stderr_text = stderr_data.decode('utf-8', errors='replace') if stderr_data else '(no stderr)'
        logger.error(
            "git-http-backend failed (rc=%d) for repo=%s path=%s: %s",
            proc.returncode, slug, git_path, stderr_text
        )
        return HttpResponse(
            f"Git backend error: {stderr_text}",
            status=500, content_type="text/plain"
        )

    # CGI outputs headers first followed by double newlines. Parse and separate them
    header_body_sep = b'\r\n\r\n'
    sep_idx = stdout_data.find(header_body_sep)
    if sep_idx == -1:
        header_body_sep = b'\n\n'
        sep_idx = stdout_data.find(header_body_sep)

    # Slice header and body byte blocks
    if sep_idx != -1:
        header_bytes = stdout_data[:sep_idx]
        body_bytes = stdout_data[sep_idx + len(header_body_sep):]
    else:
        header_bytes = b''
        body_bytes = stdout_data

    # Return body bytes as Django HTTP Response
    response = HttpResponse(body_bytes)
    
    # Propagate backend CGI headers back to client response
    for line in header_bytes.splitlines():
        if b':' in line:
            k, v = line.split(b':', 1)
            header_name = k.decode('utf-8').strip()
            header_value = v.decode('utf-8').strip()
            # Prevent duplicate response headers from being set
            if header_name.lower() not in ['content-length', 'server', 'date']:
                response[header_name] = header_value

    return response

# --- Web UI Views ---

@login_required
def repo_list(request):
    """
    Display all repositories matching user access permissions with filters and searches.
    """
    # Extract query filter values from request GET variables
    query = request.GET.get('q', '')
    visibility = request.GET.get('visibility', '')   # 'public' | 'private' | ''
    sort = request.GET.get('sort', 'updated')        # 'updated' | 'name' | 'created'
    role = request.GET.get('role', '')               # 'owner' | 'collaborator' | ''

    repos = Repository.objects.all()

    # Apply search query against name and description fields
    if query:
        repos = repos.filter(models.Q(name__icontains=query) | models.Q(description__icontains=query))

    # Restrict visible repositories for non-admin/non-superuser users
    is_admin = getattr(request.user, 'is_admin', False) or request.user.is_superuser
    if not is_admin:
        # Non-admins can only see public repositories, repositories they own, or where they are added as collaborator
        repos = repos.filter(
            models.Q(is_private=False) |
            models.Q(owner=request.user) |
            models.Q(collaborators=request.user)
        ).distinct()

    # Filter by visibility choice
    if visibility == 'public':
        repos = repos.filter(is_private=False)
    elif visibility == 'private':
        repos = repos.filter(is_private=True)

    # Filter by user role relation
    if role == 'owner':
        repos = repos.filter(owner=request.user)
    elif role == 'collaborator':
        repos = repos.filter(collaborators=request.user).distinct()

    # Apply ordering sort rules
    if sort == 'name':
        repos = repos.order_by('name')
    elif sort == 'created':
        repos = repos.order_by('-created_at')
    else:
        repos = repos.order_by('-updated_at')

    # Query pending collaboration invitations for the current logged-in user
    pending_invitations = request.user.repo_invitations.filter(is_accepted=False)

    return render(request, 'resource_hub/repo_list.html', {
        'repos': repos,
        'query': query,
        'visibility': visibility,
        'sort': sort,
        'role': role,
        'pending_invitations': pending_invitations,
        'total_count': repos.count(),
    })

@login_required
def repo_create(request):
    """
    Form view to create a repository and initialize a bare git backend on disk.
    """
    # Verify that the git command line client is installed on the host OS
    git_available = shutil.which('git') is not None
    
    if request.method == 'POST':
        # Guard clause: stop if Git client executable is missing on host system
        if not git_available:
            messages.error(
                request, 
                "Git executable not found. Please install Git and make sure it is available on your system PATH before creating repositories."
            )
            return render(request, 'resource_hub/repo_create.html')

        # Extract name, description and privacy choice
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_private = request.POST.get('is_private') == 'on'

        if not name:
            messages.error(request, "Repository name is required.")
            return render(request, 'resource_hub/repo_create.html')

        # Generate slugified name to map directory and URL routes
        slug = slugify(name)
        if Repository.objects.filter(slug=slug).exists():
            messages.error(request, f"A repository with name '{name}' already exists.")
            return render(request, 'resource_hub/repo_create.html')

        # Instantiate repository record
        repo = Repository(
            name=name,
            slug=slug,
            description=description,
            owner=request.user,
            is_private=is_private
        )

        try:
            # Create the git directory on disk (ensuring parent directories exist)
            os.makedirs(os.path.dirname(repo.git_dir), exist_ok=True)
            # Initialize bare repository using subprocess command
            subprocess.run(['git', 'init', '--bare', repo.git_dir], check=True)
            
            # Configure http.receivepack config to allow remote git push commands over HTTP protocol
            subprocess.run([
                'git', 'config', '-f', os.path.join(repo.git_dir, 'config'), 'http.receivepack', 'true'
            ], check=True)

            # Save model record to database only after successful filesystem init
            repo.save()
            messages.success(request, f"Repository '{name}' created successfully.")
            return redirect('resource_hub:repo_code', slug=repo.slug)
        except Exception as e:
            # Rollback: Clean up disk files on initialization failures
            if os.path.exists(repo.git_dir):
                shutil.rmtree(repo.git_dir)
            messages.error(request, f"Error initializing git repository: {e}")

    return render(request, 'resource_hub/repo_create.html')

@login_required
def repo_code(request, slug, path=''):
    """
    Explore repository source code files and directory folders recursively.
    """
    # Retrieve repository and check user access privileges
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo)
    if not has_access:
        return HttpResponseForbidden("You do not have access to this repository.")

    # Determine if git logs contain any commit history
    empty = is_repo_empty(repo.git_dir)
    branches = get_branches(repo.git_dir)
    default_branch = get_default_branch(repo.git_dir)
    
    # Extract reference branch/commit query param, fallback to default branch
    ref = request.GET.get('ref', default_branch)
    if not ref:
        ref = default_branch

    # Construct the HTTP clone URL configuration for UI display
    clone_url = get_clone_url(request, repo)

    if empty:
        # Render empty helper onboarding template instructions if no commits exist yet
        return render(request, 'resource_hub/repo_code.html', {
            'repo': repo,
            'is_owner_or_admin': is_owner_or_admin,
            'empty': True,
            'clone_url': clone_url,
            'default_branch': default_branch
        })

    # Verify if target path resolves to a file or directory
    obj_type = get_object_type(repo.git_dir, ref, path)
    if obj_type == 'blob':
        # Redirect file paths to dedicated file viewer view
        return redirect(reverse('resource_hub:repo_file_view', kwargs={'slug': slug, 'ref': ref, 'path': path}))

    # Retrieve latest commit details for the selected reference branch/commit
    latest_commit = None
    try:
        proc = subprocess.run([
            'git', '-C', repo.git_dir, 'log', '-1', ref,
            '--pretty=format:%H|%an|%ae|%ad|%s',
            '--date=format:%Y-%m-%d %H:%M:%S'
        ], capture_output=True, text=True, check=True)
        if proc.stdout.strip():
            parts = proc.stdout.strip().split('|', 4)
            if len(parts) >= 5:
                c_hash, c_author, c_email, c_date, c_msg = parts
                latest_commit = {
                    'hash': c_hash,
                    'short_hash': c_hash[:7],
                    'author': c_author,
                    'email': c_email,
                    'date': c_date,
                    'message': c_msg
                }
    except Exception:
        pass

    # Fetch items inside target directory using git ls-tree command
    items = []
    readme_content = None
    target_dir = f"{ref}:{path}" if path else ref

    try:
        proc = subprocess.run(['git', '-C', repo.git_dir, 'ls-tree', '-l', target_dir], capture_output=True, text=True, check=True)
        for line in proc.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split(maxsplit=4)
            if len(parts) >= 5:
                mode, item_type, sha, size, name = parts
                item_path = os.path.join(path, name) if path else name
                
                # Check for README.md document to display below folder view
                if name.lower() == 'readme.md' and item_type == 'blob':
                    try:
                        readme_proc = subprocess.run(['git', '-C', repo.git_dir, 'show', f"{ref}:{item_path}"], capture_output=True, text=True)
                        if readme_proc.returncode == 0:
                            readme_content = readme_proc.stdout
                    except Exception:
                        pass

                # Query the latest commit log that modified this specific file or directory
                commit_message = ""
                commit_time = ""
                try:
                    log_proc = subprocess.run([
                        'git', '-C', repo.git_dir, 'log', '-1', ref,
                        '--pretty=format:%s|%cd', '--date=relative', '--', item_path
                    ], capture_output=True, text=True)
                    if log_proc.returncode == 0 and log_proc.stdout.strip():
                        parts_log = log_proc.stdout.strip().split('|', 1)
                        if len(parts_log) >= 2:
                            commit_message, commit_time = parts_log
                        elif len(parts_log) == 1:
                            commit_message = parts_log[0]
                except Exception:
                    pass

                # Append item mapping details
                items.append({
                    'mode': mode,
                    'type': item_type,
                    'sha': sha,
                    'size': int(size) if size.isdigit() else 0,
                    'name': name,
                    'path': item_path,
                    'commit_message': commit_message,
                    'commit_time': commit_time,
                })
    except Exception:
        # Silently skip if path doesn't exist on this reference branch
        pass

    # Sort items putting directory folders first, followed by files alphabetically
    items.sort(key=lambda x: (x['type'] != 'tree', x['name'].lower()))

    # Compile breadcrumb structure for navigation headers
    breadcrumbs = []
    if path:
        parts = path.split('/')
        current_path = ""
        for p in parts:
            current_path = os.path.join(current_path, p) if current_path else p
            breadcrumbs.append({'name': p, 'path': current_path})

    # Fetch recursive files list to power fuzzy finder search tool ("Go to file")
    all_files = []
    try:
        find_proc = subprocess.run([
            'git', '-C', repo.git_dir, 'ls-tree', '-r', '--name-only', ref
        ], capture_output=True, text=True)
        if find_proc.returncode == 0:
            all_files = [f.strip() for f in find_proc.stdout.split('\n') if f.strip()]
    except Exception:
        pass

    return render(request, 'resource_hub/repo_code.html', {
        'repo': repo,
        'is_owner_or_admin': is_owner_or_admin,
        'empty': False,
        'items': items,
        'path': path,
        'breadcrumbs': breadcrumbs,
        'branches': branches,
        'ref': ref,
        'clone_url': clone_url,
        'readme_content': readme_content,
        'default_branch': default_branch,
        'latest_commit': latest_commit,
        'all_files': all_files
    })

@login_required
def repo_file_view(request, slug, ref, path):
    """
    View file content with revision selector and syntax highlighting.
    """
    # Retrieve repository and check permissions
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo)
    if not has_access:
        return HttpResponseForbidden("You do not have access to this repository.")

    # Guard clause: verify that the target object is indeed a blob (file)
    obj_type = get_object_type(repo.git_dir, ref, path)
    if obj_type != 'blob':
        raise Http404("File not found")

    # Fetch raw file content bytes from git repository database
    proc = subprocess.run(['git', '-C', repo.git_dir, 'show', f"{ref}:{path}"], capture_output=True)
    content_bytes = proc.stdout

    # Detect binary files (containing null bytes in initial chunk)
    is_binary = b'\x00' in content_bytes[:4096]
    content = None
    if not is_binary:
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to Latin-1 encoding if UTF-8 fails
            content = content_bytes.decode('latin-1', errors='ignore')

    # Detect programming language by extension to apply syntax styling rules
    _, ext = os.path.splitext(path)
    ext = ext.lower().lstrip('.')
    lang_mapping = {
        'py': 'python', 'js': 'javascript', 'html': 'html', 'css': 'css',
        'sh': 'bash', 'json': 'json', 'md': 'markdown', 'txt': 'plaintext',
        'sql': 'sql', 'xml': 'xml', 'yaml': 'yaml', 'yml': 'yaml'
    }
    lang = lang_mapping.get(ext, ext or 'plaintext')

    # Assess if file is an image format
    is_image = ext in ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']

    # Compile navigation breadcrumbs
    breadcrumbs = []
    parts = path.split('/')
    current_path = ""
    for p in parts:
        current_path = os.path.join(current_path, p) if current_path else p
        breadcrumbs.append({'name': p, 'path': current_path})

    branches = get_branches(repo.git_dir)
    line_count = len(content.splitlines()) if content else 0

    return render(request, 'resource_hub/repo_file_view.html', {
        'repo': repo,
        'is_owner_or_admin': is_owner_or_admin,
        'path': path,
        'breadcrumbs': breadcrumbs,
        'content': content,
        'is_binary': is_binary,
        'is_image': is_image,
        'lang': lang,
        'ref': ref,
        'branches': branches,
        'line_count': line_count,
        'clone_url': get_clone_url(request, repo),
    })

@login_required
def repo_raw_view(request, slug, ref, path):
    """
    Directly serve raw file bytes (supporting direct images, pdfs, and download assets).
    """
    # Retrieve repository and verify user access
    repo = get_object_or_404(Repository, slug=slug)
    has_access, _ = check_repo_access(request, repo)
    if not has_access:
        return HttpResponseForbidden("You do not have access to this repository.")

    # Retrieve raw file content
    proc = subprocess.run(['git', '-C', repo.git_dir, 'show', f"{ref}:{path}"], capture_output=True)
    if proc.returncode != 0:
        raise Http404("File not found")

    content_bytes = proc.stdout
    _, ext = os.path.splitext(path)
    ext = ext.lower().lstrip('.')
    
    # Map basic MIME content types based on file extension
    ct_mapping = {
        'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'gif': 'image/gif', 'webp': 'image/webp', 'svg': 'image/svg+xml',
        'pdf': 'application/pdf', 'txt': 'text/plain', 'html': 'text/html',
        'css': 'text/css', 'js': 'application/javascript', 'json': 'application/json'
    }
    content_type = ct_mapping.get(ext, 'application/octet-stream')

    # Return response payload
    response = HttpResponse(content_bytes, content_type=content_type)
    # Add attachment headers for unrecognized binary files to force downloads
    if content_type == 'application/octet-stream':
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
    return response

@login_required
def repo_commits(request, slug):
    """
    View chronological git commit log for the selected branch/reference.
    """
    # Retrieve repository and check permissions
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo)
    if not has_access:
        return HttpResponseForbidden("You do not have access to this repository.")

    # Redirect to files view if no commits exist
    empty = is_repo_empty(repo.git_dir)
    if empty:
        return redirect('resource_hub:repo_code', slug=repo.slug)

    # Get active reference and branch list
    ref = request.GET.get('ref', get_default_branch(repo.git_dir))
    branches = get_branches(repo.git_dir)

    commits = []
    try:
        # Run git log with a piped format string parsing: Hash|Author|Email|Date|Message
        proc = subprocess.run([
            'git', '-C', repo.git_dir, 'log', ref, '--pretty=format:%H|%an|%ae|%ad|%s', '--date=format:%Y-%m-%d %H:%M:%S'
        ], capture_output=True, text=True, check=True)
        
        # Parse stdout log lines
        for line in proc.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 4)
            if len(parts) >= 5:
                commit_hash, author, email, date, message = parts
                commits.append({
                    'hash': commit_hash,
                    'short_hash': commit_hash[:7],
                    'author': author,
                    'email': email,
                    'date': date,
                    'message': message,
                })
    except Exception:
        pass

    return render(request, 'resource_hub/repo_commits.html', {
        'repo': repo,
        'is_owner_or_admin': is_owner_or_admin,
        'commits': commits,
        'ref': ref,
        'branches': branches,
        'clone_url': get_clone_url(request, repo),
    })

@login_required
def repo_commit_detail(request, slug, commit_hash):
    """
    Parse and view patch code diff of a single git commit.
    """
    # Retrieve repository and check permissions
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo)
    if not has_access:
        return HttpResponseForbidden("You do not have access to this repository.")

    try:
        # Fetch metadata details for this single commit hash
        proc_meta = subprocess.run([
            'git', '-C', repo.git_dir, 'show', '--pretty=format:%H|%an|%ae|%ad|%s', '--date=format:%Y-%m-%d %H:%M:%S', '-s', commit_hash
        ], capture_output=True, text=True, check=True)
        parts = proc_meta.stdout.strip().split('|', 4)
        if len(parts) < 5:
            raise Http404("Commit details not found")
        
        c_hash, author, email, date, message = parts
        commit_info = {
            'hash': c_hash,
            'short_hash': c_hash[:7],
            'author': author,
            'email': email,
            'date': date,
            'message': message
        }

        # Fetch full diff code patch details
        proc_diff = subprocess.run([
            'git', '-C', repo.git_dir, 'show', '--patch', commit_hash
        ], capture_output=True, text=True, check=True)
        
        # Initialize parser variables to separate modified files
        diff_files = []
        current_file = None
        
        lines = proc_diff.stdout.split('\n')
        # Git show includes a commit header block before the first file diff
        in_diff_sec = False
        
        for line in lines:
            # Detect starting point of a new file diff
            if line.startswith('diff --git '):
                in_diff_sec = True
                parts_line = line.split(' ')
                file_a = parts_line[2][2:] if len(parts_line) > 2 else ""
                file_b = parts_line[3][2:] if len(parts_line) > 3 else ""
                
                # Setup structured dictionary representing file changes
                current_file = {
                    'old_path': file_a,
                    'new_path': file_b,
                    'lines': [],
                    'status': 'modified',
                    'added_count': 0,
                    'deleted_count': 0
                }
                diff_files.append(current_file)
                continue

            # Skip parsing until we reach files section
            if not in_diff_sec or current_file is None:
                continue

            # Detect modifications status (creation, deletion, renamed)
            if line.startswith('new file mode '):
                current_file['status'] = 'created'
                continue
            elif line.startswith('deleted file mode '):
                current_file['status'] = 'deleted'
                continue
            elif line.startswith('rename from '):
                current_file['status'] = 'renamed'
                continue

            if line.startswith('--- '):
                continue
            elif line.startswith('+++ '):
                continue
            
            # Map lines into added, deleted or normal blocks
            if line.startswith('@@ '):
                current_file['lines'].append({'type': 'info', 'text': line})
            elif line.startswith('+'):
                current_file['lines'].append({'type': 'added', 'text': line})
                current_file['added_count'] += 1
            elif line.startswith('-'):
                current_file['lines'].append({'type': 'deleted', 'text': line})
                current_file['deleted_count'] += 1
            else:
                current_file['lines'].append({'type': 'normal', 'text': line})

        # Enrich diff files with metadata for binary/image rendering in templates
        for f_data in diff_files:
            target_path = f_data['new_path'] or f_data['old_path']
            _, ext = os.path.splitext(target_path)
            ext = ext.lower().lstrip('.')
            f_data['is_image'] = ext in ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']
            
            # Identify binary modifications
            is_binary = False
            for line_item in f_data['lines']:
                if 'Binary files' in line_item['text'] and 'differ' in line_item['text']:
                    is_binary = True
                    break
            f_data['is_binary'] = is_binary

    except Exception as e:
        raise Http404(f"Commit diff failed: {e}")

    return render(request, 'resource_hub/repo_commit_detail.html', {
        'repo': repo,
        'is_owner_or_admin': is_owner_or_admin,
        'commit': commit_info,
        'diff_files': diff_files,
        'clone_url': get_clone_url(request, repo),
        'active_tab': 'commits',
    })

@login_required
def repo_upload(request, slug):
    """
    Form view supporting multi-file direct uploads to the bare git repository.
    Handles temporary directory clones and automated pushes.
    """
    # Retrieve repository and enforce strict write (require_write=True) access check
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo, require_write=True)
    if not has_access:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'error': 'You do not have permission to upload to this repository.'}, status=403)
        return HttpResponseForbidden("You do not have permission to upload to this repository.")

    default_branch = get_default_branch(repo.git_dir)
    branches = get_branches(repo.git_dir)

    if request.method == 'POST':
        # Retrieve form parameters
        commit_message = request.POST.get('commit_message', '').strip()
        branch = request.POST.get('branch', default_branch).strip()
        files = request.FILES.getlist('files')
        paths = request.POST.getlist('paths')

        # Detect AJAX uploads
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

        clone_url = get_clone_url(request, repo)
        if not commit_message:
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({'success': False, 'error': 'Commit message is required.'}, status=400)
            messages.error(request, "Commit message is required.")
            return render(request, 'resource_hub/repo_upload.html', {'repo': repo, 'branches': branches, 'default_branch': default_branch, 'is_owner_or_admin': is_owner_or_admin, 'clone_url': clone_url})

        if not files:
            if is_ajax:
                from django.http import JsonResponse
                return JsonResponse({'success': False, 'error': 'At least one file must be selected.'}, status=400)
            messages.error(request, "At least one file must be selected.")
            return render(request, 'resource_hub/repo_upload.html', {'repo': repo, 'branches': branches, 'default_branch': default_branch, 'is_owner_or_admin': is_owner_or_admin, 'clone_url': clone_url})

        # Process upload via temporary working directory clone of the bare git repository
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                is_empty = is_repo_empty(repo.git_dir)
                
                if is_empty:
                    # Initialize fresh empty git repository inside the temp folder and add bare repo as origin
                    subprocess.run(['git', 'init', temp_dir], check=True)
                    subprocess.run(['git', '-C', temp_dir, 'remote', 'add', 'origin', repo.git_dir], check=True)
                    subprocess.run(['git', '-C', temp_dir, 'checkout', '-b', branch], check=True)
                else:
                    # Clone bare repo to temp directory
                    subprocess.run(['git', 'clone', repo.git_dir, temp_dir], check=True)
                    
                    # Verify if target branch already exists, checkout or create it
                    proc_check = subprocess.run(['git', '-C', temp_dir, 'show-ref', '--verify', f"refs/heads/{branch}"], capture_output=True)
                    if proc_check.returncode == 0:
                        subprocess.run(['git', '-C', temp_dir, 'checkout', branch], check=True)
                    else:
                        subprocess.run(['git', '-C', temp_dir, 'checkout', '-b', branch], check=True)

                # Write files into temporary clone directory structure
                for idx, f in enumerate(files):
                    rel_path = paths[idx] if idx < len(paths) else f.name
                    # Sanitize destination path to prevent path traversal vulnerabilities
                    rel_path = os.path.normpath(rel_path).lstrip('/')
                    if rel_path.startswith('..') or os.path.isabs(rel_path):
                        continue
                        
                    file_path = os.path.join(temp_dir, rel_path)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'wb+') as dest:
                        for chunk in f.chunks():
                            dest.write(chunk)

                # Configure local author identity details for the git commit
                author_name = request.user.display_name or request.user.username
                author_email = request.user.email or f"{request.user.username}@local.com"

                subprocess.run(['git', '-C', temp_dir, 'config', 'user.name', author_name], check=True)
                subprocess.run(['git', '-C', temp_dir, 'config', 'user.email', author_email], check=True)
                subprocess.run(['git', '-C', temp_dir, 'add', '.'], check=True)
                
                # Commit modifications
                commit_proc = subprocess.run(['git', '-C', temp_dir, 'commit', '-m', commit_message], capture_output=True, text=True)
                if commit_proc.returncode == 0:
                    # Push back to bare repository origin
                    if is_empty:
                        subprocess.run(['git', '-C', temp_dir, 'push', '-u', 'origin', branch], check=True)
                        # Set default branch HEAD configuration on bare repository
                        subprocess.run(['git', '-C', repo.git_dir, 'symbolic-ref', 'HEAD', f"refs/heads/{branch}"], check=True)
                    else:
                        subprocess.run(['git', '-C', temp_dir, 'push', 'origin', branch], check=True)
                    
                    # Log web upload action in audit logs
                    desc = f"Web upload of {len(files)} files/folders to branch '{branch}'"
                    try:
                        ip = get_client_ip(request)
                        RepoActivityLog.objects.create(
                            repository=repo,
                            user=request.user,
                            action='web_upload',
                            description=desc,
                            ip_address=ip
                        )
                    except Exception:
                        pass

                    if is_ajax:
                        from django.http import JsonResponse
                        messages.success(request, f"Successfully uploaded and committed resources to branch '{branch}'.")
                        return JsonResponse({'success': True, 'redirect_url': reverse('resource_hub:repo_code', kwargs={'slug': repo.slug})})
                    
                    messages.success(request, f"Successfully uploaded and committed resources to branch '{branch}'.")
                    return redirect('resource_hub:repo_code', slug=repo.slug)
                else:
                    if is_ajax:
                        from django.http import JsonResponse
                        return JsonResponse({'success': False, 'error': 'No changes detected. Nothing to commit.'}, status=400)
                    messages.warning(request, "No changes detected. Nothing to commit.")
                    return redirect('resource_hub:repo_code', slug=repo.slug)

            except Exception as e:
                if is_ajax:
                    from django.http import JsonResponse
                    return JsonResponse({'success': False, 'error': f"An error occurred during commit/push: {e}"}, status=500)
                messages.error(request, f"An error occurred during commit/push: {e}")

    return render(request, 'resource_hub/repo_upload.html', {
        'repo': repo,
        'branches': branches,
        'default_branch': default_branch,
        'is_owner_or_admin': is_owner_or_admin,
        'clone_url': get_clone_url(request, repo),
    })

@login_required
def repo_settings(request, slug):
    """
    View/edit repository settings (rename, toggle visibility, delete, collaborators).
    """
    # Retrieve repository and enforce write checks
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo, require_write=True)
    if not has_access:
        return HttpResponseForbidden("You do not have permission to access these settings.")

    from django.contrib.auth import get_user_model
    User = get_user_model()
    clone_url = get_clone_url(request, repo)

    if request.method == 'POST':
        # Guard clause: restrict write settings to owner or admin
        if not is_owner_or_admin:
            return HttpResponseForbidden("Only the repository owner or administrator can modify these settings.")

        action = request.POST.get('action')

        # Action: Update name, description, privacy settings
        if action == 'update':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            is_private = request.POST.get('is_private') == 'on'

            if not name:
                messages.error(request, "Repository name is required.")
                return redirect('resource_hub:repo_settings', slug=repo.slug)

            new_slug = slugify(name)
            if new_slug != repo.slug and Repository.objects.filter(slug=new_slug).exists():
                messages.error(request, f"A repository with name '{name}' already exists.")
                return redirect('resource_hub:repo_settings', slug=repo.slug)

            # Rename physical git bare repository directory if the slug has changed
            if new_slug != repo.slug:
                old_dir = repo.git_dir
                repo.slug = new_slug
                new_dir = repo.git_dir
                try:
                    if os.path.exists(old_dir):
                        os.makedirs(os.path.dirname(new_dir), exist_ok=True)
                        os.rename(old_dir, new_dir)
                except Exception as e:
                    messages.error(request, f"Failed to rename git directory: {e}")
                    return redirect('resource_hub:repo_settings', slug=repo.slug)

            # Persist model modifications
            repo.name = name
            repo.description = description
            repo.is_private = is_private
            repo.save()

            messages.success(request, "Repository configuration updated successfully.")
            return redirect('resource_hub:repo_code', slug=repo.slug)

        # Action: Invite new user as a collaborator
        elif action == 'add_collaborator':
            user_id = request.POST.get('user_id')
            if user_id:
                try:
                    user_to_add = User.objects.get(pk=user_id)
                    if user_to_add == repo.owner:
                        messages.error(request, "You cannot add the owner as a collaborator.")
                    elif repo.collaborators.filter(pk=user_to_add.pk).exists():
                        messages.error(request, f"{user_to_add.username} is already a collaborator.")
                    elif RepoInvitation.objects.filter(repository=repo, invitee=user_to_add, is_accepted=False).exists():
                        messages.error(request, f"An invitation has already been sent to {user_to_add.username}.")
                    else:
                        # Instantiate pending RepoInvitation record
                        RepoInvitation.objects.create(
                            repository=repo,
                            invitee=user_to_add,
                            invited_by=request.user
                        )
                        # Dispatch real-time user notification
                        from notifications.models import Notification
                        Notification.objects.create(
                            recipient=user_to_add,
                            sender=request.user,
                            notification_type='repo_invite',
                            title='Repository Collaboration Invitation',
                            message=f"{request.user.display_name} has invited you to collaborate on the repository '{repo.name}'."
                        )
                        messages.success(request, f"Invitation sent to {user_to_add.username}.")
                except User.DoesNotExist:
                    messages.error(request, "Selected user does not exist.")
            return redirect('resource_hub:repo_settings', slug=repo.slug)

        # Action: Cancel a pending collaborator invitation
        elif action == 'cancel_invitation':
            invite_id = request.POST.get('invite_id')
            if invite_id:
                try:
                    invite = RepoInvitation.objects.get(pk=invite_id, repository=repo, is_accepted=False)
                    invitee_username = invite.invitee.username
                    
                    # Delete the dispatched invite notification
                    from notifications.models import Notification
                    Notification.objects.filter(
                        recipient=invite.invitee,
                        notification_type='repo_invite',
                        message__icontains=repo.name
                    ).delete()
                    
                    invite.delete()
                    messages.success(request, f"Cancelled invitation to {invitee_username}.")
                except RepoInvitation.DoesNotExist:
                    messages.error(request, "Invitation does not exist.")
            return redirect('resource_hub:repo_settings', slug=repo.slug)

        # Action: Remove an active collaborator from access list
        elif action == 'remove_collaborator':
            user_id = request.POST.get('user_id')
            if user_id:
                try:
                    user_to_remove = User.objects.get(pk=user_id)
                    repo.collaborators.remove(user_to_remove)
                    # Audit-log collaborator removal action
                    ip = get_client_ip(request)
                    RepoActivityLog.objects.create(
                        repository=repo,
                        user=request.user,
                        action='remove_collaborator',
                        description=f"Removed collaborator {user_to_remove.username}",
                        ip_address=ip
                    )
                    messages.success(request, f"Removed {user_to_remove.username} from collaborators.")
                except User.DoesNotExist:
                    messages.error(request, "Selected user does not exist.")
            return redirect('resource_hub:repo_settings', slug=repo.slug)

        # Action: Confirm and delete repository completely
        elif action == 'delete':
            confirm_name = request.POST.get('confirm_name', '').strip()
            if confirm_name != repo.name:
                messages.error(request, "Incorrect confirmation. Repository was not deleted.")
                return redirect('resource_hub:repo_settings', slug=repo.slug)

            repo_name = repo.name
            repo.delete() # Cleans up disk folder via custom overridden delete() method in models.py
            messages.success(request, f"Repository '{repo_name}' deleted successfully.")
            return redirect('resource_hub:repo_list')

    # Query active collaborators and pending invites
    collaborators = repo.collaborators.all()
    pending_invites = repo.invitations.filter(is_accepted=False)
    
    # Calculate set of available active users who can be invited (excluding owner, existing collaborators, and pending invitees)
    exclude_pks = [repo.owner.pk]
    exclude_pks.extend(collaborators.values_list('pk', flat=True))
    exclude_pks.extend(pending_invites.values_list('invitee__pk', flat=True))
    
    available_users = User.objects.exclude(pk__in=exclude_pks).filter(is_active=True)

    return render(request, 'resource_hub/repo_settings.html', {
        'repo': repo,
        'is_owner_or_admin': is_owner_or_admin,
        'clone_url': clone_url,
        'collaborators': collaborators,
        'pending_invites': pending_invites,
        'available_users': available_users,
        'active_tab': 'settings'
    })

@login_required
def repo_user_guide(request, slug):
    """
    Serve a complete repository user guide with setup instructions.
    """
    # Retrieve repository and check permissions
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo)
    if not has_access:
        return HttpResponseForbidden("You do not have access to this repository.")

    # Build the full absolute HTTP clone URL for command-line instructions
    clone_url = request.build_absolute_uri(
        reverse('resource_hub:git_smart_http', kwargs={'slug': repo.slug, 'git_path': 'info/refs'})
    )
    if clone_url.endswith('/info/refs'):
        clone_url = clone_url[:-10]

    return render(request, 'resource_hub/repo_user_guide.html', {
        'repo': repo,
        'clone_url': clone_url,
        'active_tab': 'guide',
        'is_owner_or_admin': is_owner_or_admin,
    })

@login_required
def repo_logs(request, slug):
    """
    View repository activity logs, visible only to the repository creator.
    """
    # Retrieve repository and check permissions
    repo = get_object_or_404(Repository, slug=slug)
    
    # Restrict to repository owner (creator) as a security gate
    if request.user != repo.owner:
        return HttpResponseForbidden("Only the repository creator can view repository access and activity logs.")

    _, is_owner_or_admin = check_repo_access(request, repo)
    
    # Fetch chronological activity log entries
    logs = RepoActivityLog.objects.filter(repository=repo)

    return render(request, 'resource_hub/repo_logs.html', {
        'repo': repo,
        'logs': logs,
        'active_tab': 'logs',
        'is_owner_or_admin': is_owner_or_admin,
        'clone_url': get_clone_url(request, repo),
    })

@login_required
def repo_download_zip(request, slug, ref):
    """
    Generate and return a ZIP archive of the repository at the specified reference.
    Uses Git's native archive subsystem to construct zip streams efficiently.
    """
    # Retrieve repository and check permissions
    repo = get_object_or_404(Repository, slug=slug)
    has_access, _ = check_repo_access(request, repo)
    if not has_access:
        return HttpResponseForbidden("You do not have permission to access this repository.")

    if is_repo_empty(repo.git_dir):
        return HttpResponse("Repository is empty.", status=400)

    try:
        # Generate archive using git archive subprocess command
        proc = subprocess.run([
            'git', '-C', repo.git_dir, 'archive', '--format=zip',
            f'--prefix={repo.slug}-{ref}/', ref
        ], capture_output=True, check=True)
        
        # Log download action in audit logs
        try:
            ip = get_client_ip(request)
            RepoActivityLog.objects.create(
                repository=repo,
                user=request.user,
                action='download_zip',
                description=f"Downloaded repository ZIP archive for reference '{ref}'",
                ip_address=ip
            )
        except Exception:
            pass

        # Sanitize reference branch name to safe characters for filenames
        safe_ref = ref.replace('/', '-')
        
        # Construct and return zip stream response object
        response = HttpResponse(proc.stdout, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{repo.slug}-{safe_ref}.zip"'
        response['Content-Length'] = len(proc.stdout)
        return response
    except Exception as e:
        return HttpResponse(f"Failed to generate archive: {e}", status=500)

@login_required
def repo_create_file(request, slug):
    """
    Provide a web interface to create and commit a new file directly to the git repository.
    """
    # Retrieve repository and check write access permission
    repo = get_object_or_404(Repository, slug=slug)
    has_access, is_owner_or_admin = check_repo_access(request, repo, require_write=True)
    if not has_access:
        return HttpResponseForbidden("You do not have permission to write to this repository.")

    default_branch = get_default_branch(repo.git_dir)
    branches = get_branches(repo.git_dir)
    clone_url = get_clone_url(request, repo)

    if request.method == 'POST':
        # Retrieve form parameters
        file_path = request.POST.get('file_path', '').strip().lstrip('/')
        file_content = request.POST.get('file_content', '')
        commit_message = request.POST.get('commit_message', '').strip()
        branch = request.POST.get('branch', default_branch).strip()

        if not file_path:
            messages.error(request, "File path is required.")
            return render(request, 'resource_hub/repo_create_file.html', {
                'repo': repo, 'branches': branches, 'default_branch': default_branch,
                'is_owner_or_admin': is_owner_or_admin, 'clone_url': clone_url
            })

        # Sanitize destination path to prevent path traversal vulnerability
        file_path = os.path.normpath(file_path).lstrip('/')
        if file_path.startswith('..') or os.path.isabs(file_path):
            messages.error(request, "Invalid file path.")
            return render(request, 'resource_hub/repo_create_file.html', {
                'repo': repo, 'branches': branches, 'default_branch': default_branch,
                'is_owner_or_admin': is_owner_or_admin, 'clone_url': clone_url
            })

        if not commit_message:
            commit_message = f"Create {file_path}"

        # Write the file inside a temporary repository clone and push it back to the bare repository
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                is_empty = is_repo_empty(repo.git_dir)
                
                if is_empty:
                    # Initialize a fresh git repository inside the temp directory
                    subprocess.run(['git', 'init', temp_dir], check=True)
                    subprocess.run(['git', '-C', temp_dir, 'remote', 'add', 'origin', repo.git_dir], check=True)
                    subprocess.run(['git', '-C', temp_dir, 'checkout', '-b', branch], check=True)
                else:
                    # Clone the bare repository into temp folder
                    subprocess.run(['git', 'clone', repo.git_dir, temp_dir], check=True)
                    proc_check = subprocess.run(['git', '-C', temp_dir, 'show-ref', '--verify', f"refs/heads/{branch}"], capture_output=True)
                    if proc_check.returncode == 0:
                        subprocess.run(['git', '-C', temp_dir, 'checkout', branch], check=True)
                    else:
                        subprocess.run(['git', '-C', temp_dir, 'checkout', '-b', branch], check=True)

                # Write content to the targeted file
                full_dest_path = os.path.join(temp_dir, file_path)
                os.makedirs(os.path.dirname(full_dest_path), exist_ok=True)
                with open(full_dest_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)

                # Configure local author details for git commit
                author_name = request.user.display_name or request.user.username
                author_email = request.user.email or f"{request.user.username}@local.com"

                subprocess.run(['git', '-C', temp_dir, 'config', 'user.name', author_name], check=True)
                subprocess.run(['git', '-C', temp_dir, 'config', 'user.email', author_email], check=True)
                subprocess.run(['git', '-C', temp_dir, 'add', '.'], check=True)

                # Commit changes
                commit_proc = subprocess.run(['git', '-C', temp_dir, 'commit', '-m', commit_message], capture_output=True, text=True)
                if commit_proc.returncode == 0:
                    # Push back to bare repository origin
                    if is_empty:
                        subprocess.run(['git', '-C', temp_dir, 'push', '-u', 'origin', branch], check=True)
                        subprocess.run(['git', '-C', repo.git_dir, 'symbolic-ref', 'HEAD', f"refs/heads/{branch}"], check=True)
                    else:
                        subprocess.run(['git', '-C', temp_dir, 'push', 'origin', branch], check=True)

                    # Log file creation action in audit logs
                    try:
                        ip = get_client_ip(request)
                        RepoActivityLog.objects.create(
                            repository=repo,
                            user=request.user,
                            action='create_file',
                            description=f"Created file '{file_path}' in branch '{branch}'",
                            ip_address=ip
                        )
                    except Exception:
                        pass

                    messages.success(request, f"Successfully created and committed '{file_path}' to branch '{branch}'.")
                    
                    # Redirect back to folder directory page view
                    dir_path = os.path.dirname(file_path)
                    if dir_path:
                        return redirect(reverse('resource_hub:repo_code_dir', kwargs={'slug': repo.slug, 'path': dir_path}) + f"?ref={branch}")
                    else:
                        return redirect(reverse('resource_hub:repo_code', kwargs={'slug': repo.slug}) + f"?ref={branch}")
                else:
                    messages.warning(request, "No changes detected or file creation failed.")
                    return redirect('resource_hub:repo_code', slug=repo.slug)

            except Exception as e:
                messages.error(request, f"An error occurred while creating the file: {e}")
                return redirect('resource_hub:repo_code', slug=repo.slug)

    return render(request, 'resource_hub/repo_create_file.html', {
        'repo': repo,
        'branches': branches,
        'default_branch': default_branch,
        'is_owner_or_admin': is_owner_or_admin,
        'clone_url': clone_url,
    })

@login_required
def repo_accept_invite(request, invite_id):
    """
    Accept collaborator invitation, grant access to repository, and log activity.
    """
    invite = get_object_or_404(RepoInvitation, pk=invite_id, invitee=request.user, is_accepted=False)
    repo = invite.repository
    
    # Associate user into repository collaborators list
    repo.collaborators.add(request.user)
    invite.is_accepted = True
    invite.save()
    
    # Mark invitation-related notifications as read automatically
    from notifications.models import Notification
    Notification.objects.filter(
        recipient=request.user, 
        notification_type='repo_invite',
        message__icontains=repo.name
    ).update(is_read=True)
    
    # Log acceptance activity log
    ip = get_client_ip(request)
    RepoActivityLog.objects.create(
        repository=repo,
        user=request.user,
        action='accept_invite',
        description=f"Accepted collaborator invitation",
        ip_address=ip
    )
    
    messages.success(request, f"You are now a collaborator on '{repo.name}'.")
    return redirect('resource_hub:repo_code', slug=repo.slug)

@login_required
def repo_decline_invite(request, invite_id):
    """
    Decline collaborator invitation and clean up notification entries.
    """
    invite = get_object_or_404(RepoInvitation, pk=invite_id, invitee=request.user, is_accepted=False)
    repo = invite.repository
    invite.delete()
    
    # Mark invitation-related notifications as read automatically
    from notifications.models import Notification
    Notification.objects.filter(
        recipient=request.user, 
        notification_type='repo_invite',
        message__icontains=repo.name
    ).update(is_read=True)
    
    messages.success(request, f"Declined invitation to collaborate on '{repo.name}'.")
    return redirect('resource_hub:repo_list')
