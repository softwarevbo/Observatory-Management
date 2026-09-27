"""
tasks/services/git_service.py

Core Git integration service.
Handles SSH-key and HTTPS-token authentication, staging, committing
and pushing release files to a remote repository.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import git
from git import Repo, GitCommandError

if TYPE_CHECKING:
    from tasks.models import ProjectGitConfig, ReleaseFile


# ─── helpers ──────────────────────────────────────────────────────────────────

def _fix_perms(func, path, exc_info):
    """Error-handler for shutil.rmtree on read-only files (Windows safe)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


class GitOperationError(Exception):
    """Raised when any git operation fails."""


# ─── main service ─────────────────────────────────────────────────────────────

class GitService:
    """
    Performs git add / commit / push for a set of release files.

    Usage:
        result = GitService.push_release_files(git_config, release, file_ids, commit_msg, user)
    """

    @staticmethod
    def _write_ssh_key(private_key_text: str) -> str:
        """Write PEM key to a temp file, return path."""
        fd, path = tempfile.mkstemp(prefix="iiap_git_", suffix=".pem")
        os.close(fd)
        # Normalize CRLF (\r\n) line endings to Unix (\n) and add trailing newline
        normalized_key = private_key_text.replace("\r\n", "\n").strip() + "\n"
        with open(path, "w", newline="\n") as f:
            f.write(normalized_key)
        os.chmod(path, 0o600)
        return path

    @staticmethod
    def _git_ssh_env(key_path: str) -> dict:
        """Return GIT_SSH_COMMAND env-var pointing to the key file."""
        return {
            "GIT_SSH_COMMAND": (
                f"ssh -i {key_path} "
                "-o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null"
            ),
            **os.environ,
        }

    @staticmethod
    def _inject_token_in_url(remote_url: str, username: str, token: str) -> str:
        """Inject HTTPS token into remote URL."""
        if remote_url.startswith("https://"):
            # Strip existing username/auth info from the URL if present
            # e.g., https://username@github.com/... -> github.com/...
            url = remote_url[len("https://"):]
            if "@" in url:
                url = url.split("@", 1)[1]
            
            creds = f"{username or 'oauth2'}:{token}@"
            return f"https://{creds}{url}"
        return remote_url

    # ── public API ────────────────────────────────────────────────────────────

    @staticmethod
    def test_connection(git_config) -> dict:
        """
        Attempt to list refs on the remote to verify connectivity.
        Returns {"ok": bool, "message": str, "console_output": str}.
        """
        key_path = None
        console_output_lines = []
        try:
            env = dict(os.environ)
            env["GIT_TERMINAL_PROMPT"] = "0"
            remote_url = git_config.remote_url

            auth_masked_url = remote_url
            if git_config.auth_method == "ssh_key":
                if remote_url.startswith("http"):
                    return {
                        "ok": False,
                        "message": "Invalid configuration: You cannot use SSH Key auth with an HTTPS Remote URL. Please either use an SSH Remote URL (starting with 'git@' or 'ssh://') or change your authentication to HTTPS / Token.",
                        "console_output": "ERROR: SSH Key auth selected but Remote URL starts with http(s)."
                    }
                key_text = git_config.get_ssh_private_key()
                if not key_text:
                    return {"ok": False, "message": "No SSH private key configured.", "console_output": "ERROR: No SSH Key found in database."}
                key_path = GitService._write_ssh_key(key_text)
                env.update(GitService._git_ssh_env(key_path))
            else:
                if not remote_url.startswith("http"):
                    return {
                        "ok": False,
                        "message": "Invalid configuration: You cannot use HTTPS / Token auth with an SSH Remote URL. Please either use an HTTPS Remote URL (starting with 'https://') or change your authentication to SSH Private Key.",
                        "console_output": "ERROR: HTTPS / Token auth selected but Remote URL does not start with http."
                    }
                token = git_config.get_https_token()
                if not token:
                    return {"ok": False, "message": "No HTTPS token configured.", "console_output": "ERROR: No HTTPS Token found in database."}
                remote_url = GitService._inject_token_in_url(
                    remote_url, git_config.https_username, token
                )
                auth_masked_url = f"https://{git_config.https_username or 'oauth2'}:****@{remote_url.split('@', 1)[-1]}"

            console_output_lines.append(f"$ git ls-remote --heads {auth_masked_url}")

            result = subprocess.run(
                ["git", "ls-remote", "--heads", remote_url],
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )

            if result.stdout:
                console_output_lines.append(result.stdout.strip())
            if result.stderr:
                console_output_lines.append(result.stderr.strip())

            console_output = "\n".join(console_output_lines)

            if result.returncode == 0:
                branches = [
                    line.split("\t")[-1].replace("refs/heads/", "")
                    for line in result.stdout.strip().splitlines()
                    if line
                ]
                return {
                    "ok": True,
                    "message": f"Connected! Available branches: {', '.join(branches) or '(empty repo)'}",
                    "console_output": console_output,
                }
            return {
                "ok": False,
                "message": result.stderr.strip() or "Unknown error.",
                "console_output": console_output,
            }
        except subprocess.TimeoutExpired:
            console_output_lines.append("ERROR: Connection timed out after 20 seconds.")
            return {"ok": False, "message": "Connection timed out (20 s).", "console_output": "\n".join(console_output_lines)}
        except Exception as exc:
            console_output_lines.append(f"ERROR: {str(exc)}")
            return {"ok": False, "message": str(exc), "console_output": "\n".join(console_output_lines)}
        finally:
            if key_path and os.path.exists(key_path):
                os.remove(key_path)

    @staticmethod
    def push_release_files(
        git_config,
        release,
        release_file_ids: List[int],
        commit_message: str,
        triggered_by,
    ) -> dict:
        """
        Clone the remote repo into a temp dir, copy the selected release files
        into `release_dir` preserving subdirectory hierarchy, stage, commit and push.

        Returns:
            {
                "ok": bool,
                "commit_hash": str,
                "files_pushed": [str, ...],
                "message": str,
                "console_output": str,
            }
        """
        from tasks.models import ReleaseFile, ProjectGitPushLog

        key_path: Optional[str] = None
        work_dir: Optional[str] = None
        console_output_lines = []

        try:
            # ── resolve file objects ─────────────────────────────────────────
            release_files = ReleaseFile.objects.filter(
                pk__in=release_file_ids, release=release
            )

            # ── prepare authentication ───────────────────────────────────────
            env = dict(os.environ)
            env["GIT_TERMINAL_PROMPT"] = "0"
            clone_url = git_config.remote_url

            auth_masked_url = clone_url
            if git_config.auth_method == "ssh_key":
                if clone_url.startswith("http"):
                    raise GitOperationError(
                        "Invalid configuration: You cannot use SSH Key auth with an HTTPS Remote URL. Please either use an SSH Remote URL (starting with 'git@' or 'ssh://') or change your authentication to HTTPS / Token."
                    )
                key_text = git_config.get_ssh_private_key()
                if not key_text:
                    raise GitOperationError("SSH private key is not configured.")
                key_path = GitService._write_ssh_key(key_text)
                env.update(GitService._git_ssh_env(key_path))
            else:
                if not clone_url.startswith("http"):
                    raise GitOperationError(
                        "Invalid configuration: You cannot use HTTPS / Token auth with an SSH Remote URL. Please either use an HTTPS Remote URL (starting with 'https://') or change your authentication to SSH Private Key."
                    )
                token = git_config.get_https_token()
                if not token:
                    raise GitOperationError("HTTPS token is not configured.")
                clone_url = GitService._inject_token_in_url(
                    clone_url, git_config.https_username, token
                )
                auth_masked_url = f"https://{git_config.https_username or 'oauth2'}:****@{clone_url.split('@', 1)[-1]}"

            # ── clone or initialize repository ───────────────────────────────
            work_dir = tempfile.mkdtemp(prefix="iiap_git_push_")
            console_output_lines.append(f"# Initializing local workspace in temporary directory...")
            console_output_lines.append(f"$ git init {work_dir}")

            remote_branches = _get_remote_branches(clone_url, env)

            if git_config.branch in remote_branches:
                console_output_lines.append(f"$ git clone --depth=1 --branch={git_config.branch} {auth_masked_url} .")
                repo = Repo.clone_from(
                    clone_url,
                    work_dir,
                    env=env,
                    depth=1,
                    branch=git_config.branch,
                    no_single_branch=True,
                )
                console_output_lines.append("Cloned branch successfully.")
            elif remote_branches:
                console_output_lines.append(f"$ git clone --depth=1 {auth_masked_url} .")
                repo = Repo.clone_from(
                    clone_url,
                    work_dir,
                    env=env,
                    depth=1,
                )
                console_output_lines.append(f"$ git checkout -b {git_config.branch}")
                repo.git.checkout("-b", git_config.branch)
                console_output_lines.append(f"Switched to a new branch '{git_config.branch}'")
            else:
                console_output_lines.append(f"Remote repository is empty. Initializing new repository locally...")
                console_output_lines.append(f"$ git init && git checkout -b {git_config.branch}")
                repo = _init_empty_repo(clone_url, work_dir, git_config.branch, env)

            # ── configure git author ─────────────────────────────────────────
            with repo.config_writer() as cw:
                cw.set_value("user", "name", git_config.git_username or "IIAP-PM")
                cw.set_value("user", "email", git_config.git_email or "pm@iiap.local")
            console_output_lines.append(f"$ git config user.name \"{git_config.git_username or 'IIAP-PM'}\"")
            console_output_lines.append(f"$ git config user.email \"{git_config.git_email or 'pm@iiap.local'}\"")

            # ── copy files into work_dir ─────────────────────────────────────
            target_subdir = (
                Path(work_dir) / git_config.release_dir.lstrip("/")
                if git_config.release_dir.strip()
                else Path(work_dir)
            )
            target_subdir.mkdir(parents=True, exist_ok=True)

            pushed_names: List[str] = []
            staged_rels: List[str] = []
            console_output_lines.append("\n# Staging files (preserving folder structure)...")

            for rf in release_files:
                if not rf.file:
                    continue
                try:
                    src = rf.file.path
                    rel_path = rf.get_project_relative_path()
                    dst = target_subdir / rel_path.lstrip("/")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    # git-relative path
                    rel = str(dst.relative_to(work_dir))
                    repo.index.add([rel])
                    pushed_names.append(rf.original_name)
                    staged_rels.append(rel)
                    console_output_lines.append(f"  Staged: {rel_path} -> {rel}")
                except Exception as copy_err:
                    console_output_lines.append(f"  Failed to stage {rf.original_name}: {str(copy_err)}")
                    continue

            if not pushed_names:
                console_output_lines.append("\n# No files staged. Performing empty commit...")
                repo.git.commit("--allow-empty", "-m", commit_message)
                commit_hexsha = repo.head.commit.hexsha
                console_output_lines.append(f"$ git commit --allow-empty -m \"{commit_message}\"")
                console_output_lines.append(f"[{git_config.branch} {commit_hexsha[:7]}] {commit_message}")
                console_output_lines.append(" 0 files changed.")
                class DummyCommit:
                    hexsha = commit_hexsha
                commit = DummyCommit()
            else:
                # ── commit ───────────────────────────────────────────────────────
                commit = repo.index.commit(commit_message)
                console_output_lines.append("\n# Committing staged changes...")
                console_output_lines.append(f"$ git commit -m \"{commit_message}\"")
                console_output_lines.append(f"[{git_config.branch} {commit.hexsha[:7]}] {commit_message}")
                console_output_lines.append(f" {len(staged_rels)} files changed.")

            # ── push via subprocess (handles SSH env vars correctly) ─────────
            console_output_lines.append("\n# Pushing to remote repository...")
            console_output_lines.append(f"$ git push origin HEAD:refs/heads/{git_config.branch}")

            push_res = subprocess.run(
                ["git", "push", "origin", f"HEAD:refs/heads/{git_config.branch}"],
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if push_res.stdout:
                console_output_lines.append(push_res.stdout.strip())
            if push_res.stderr:
                console_output_lines.append(push_res.stderr.strip())

            if push_res.returncode != 0:
                raise subprocess.CalledProcessError(
                    push_res.returncode,
                    push_res.args,
                    output=push_res.stdout,
                    stderr=push_res.stderr
                )

            console_output_lines.append("Push completed successfully!")
            console_output = "\n".join(console_output_lines)

            # ── audit log ────────────────────────────────────────────────────
            ProjectGitPushLog.objects.create(
                project=git_config.project,
                release=release,
                triggered_by=triggered_by,
                commit_message=commit_message,
                commit_hash=commit.hexsha,
                branch=git_config.branch,
                remote_url=git_config.remote_url,
                files_pushed=pushed_names,
                status="success",
                terminal_output=console_output,
            )

            return {
                "ok": True,
                "commit_hash": commit.hexsha,
                "files_pushed": pushed_names,
                "message": f"Pushed {len(pushed_names)} file(s) as commit {commit.hexsha[:8]}.",
                "console_output": console_output,
            }

        except GitOperationError as exc:
            console_output_lines.append(f"ERROR: {str(exc)}")
            console_output = "\n".join(console_output_lines)
            _log_failure(git_config, release, triggered_by, commit_message, str(exc), console_output)
            return {"ok": False, "message": str(exc), "console_output": console_output}
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or "").strip()
            console_output_lines.append(f"ERROR: Git push failed (exit code {exc.returncode})")
            if err:
                console_output_lines.append(err)
            console_output = "\n".join(console_output_lines)
            _log_failure(git_config, release, triggered_by, commit_message, err, console_output)
            return {"ok": False, "message": f"Git push failed: {err}", "console_output": console_output}
        except GitCommandError as exc:
            console_output_lines.append(f"ERROR: Git command failed: {str(exc)}")
            console_output = "\n".join(console_output_lines)
            _log_failure(git_config, release, triggered_by, commit_message, str(exc), console_output)
            return {"ok": False, "message": f"Git error: {exc}", "console_output": console_output}
        except Exception as exc:
            console_output_lines.append(f"ERROR: Unexpected exception occurred: {str(exc)}")
            console_output = "\n".join(console_output_lines)
            _log_failure(git_config, release, triggered_by, commit_message, str(exc), console_output)
            return {"ok": False, "message": f"Unexpected error: {exc}", "console_output": console_output}
        finally:
            if key_path and os.path.exists(key_path):
                os.remove(key_path)
            if work_dir and os.path.isdir(work_dir):
                shutil.rmtree(work_dir, onerror=_fix_perms)


# ─── private helpers ──────────────────────────────────────────────────────────

def _get_remote_branches(url: str, env: dict) -> List[str]:
    """Get list of branches on the remote repository."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", url],
            env=env, capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return [
                line.split("\t")[-1].replace("refs/heads/", "")
                for line in result.stdout.strip().splitlines()
                if line
            ]
    except Exception:
        pass
    return []


def _init_empty_repo(clone_url: str, work_dir: str, branch: str, env: dict) -> Repo:
    """
    Initialise a brand-new local repo and set the remote when the
    remote branch does not yet exist (first push).
    """
    repo = Repo.init(work_dir)
    try:
        repo.git.checkout("-b", branch)
    except Exception:
        repo.git.branch("-m", branch)
    repo.create_remote("origin", clone_url)
    return repo


def _log_failure(git_config, release, triggered_by, commit_message, error_msg, terminal_output=""):
    """Silently write a failure log entry."""
    try:
        from tasks.models import ProjectGitPushLog
        ProjectGitPushLog.objects.create(
            project=git_config.project,
            release=release,
            triggered_by=triggered_by,
            commit_message=commit_message,
            branch=git_config.branch,
            remote_url=git_config.remote_url,
            status="failed",
            error_message=error_msg,
            terminal_output=terminal_output,
        )
    except Exception:
        pass


    @staticmethod
    def get_release_diff(
        git_config,
        release,
        release_file_ids: List[int],
    ) -> dict:
        """Calculates git diff line changes of selected release snapshot files."""
        from tasks.models import ReleaseFile
        import os
        import shutil
        import tempfile
        from pathlib import Path
        from git import Repo

        key_path = None
        work_dir = None

        try:
            release_files = ReleaseFile.objects.filter(
                pk__in=release_file_ids, release=release
            )

            env = dict(os.environ)
            env["GIT_TERMINAL_PROMPT"] = "0"
            clone_url = git_config.remote_url

            if git_config.auth_method == "ssh_key":
                key_path = GitService._write_ssh_key(git_config.ssh_private_key)
                env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
            elif git_config.auth_method == "https_token":
                token = git_config.get_https_token()
                if not token:
                    raise Exception("HTTPS token is not configured.")
                clone_url = GitService._inject_token_in_url(
                    clone_url, git_config.https_username, token
                )

            work_dir = tempfile.mkdtemp(prefix="git_diff_")
            repo = Repo.clone_from(clone_url, work_dir, env=env, branch=git_config.branch)

            target_subdir = Path(work_dir)
            pushed_names = []
            for rf in release_files:
                if not rf.file:
                    continue
                try:
                    src = rf.file.path
                    rel_path = rf.get_project_relative_path()
                    dst = target_subdir / rel_path.lstrip("/")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    rel = str(dst.relative_to(work_dir))
                    repo.index.add([rel])
                    pushed_names.append(rf.original_name)
                except Exception:
                    continue

            diff_output = repo.git.diff("HEAD")
            return {
                "ok": True,
                "diff": diff_output,
            }
        except Exception as exc:
            return {
                "ok": False,
                "message": str(exc),
            }
        finally:
            if work_dir and os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
            if key_path and os.path.exists(key_path):
                os.remove(key_path)

