"""
Workspace Isolation Layer for Sentinel.
Uses git worktree to create isolated, fast, zero-copy checkouts for each task.
Never mutates or writes to the original repository.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sentinel.sandbox.exceptions import SandboxViolation


def get_default_runs_dir() -> str:
    """Return platform-appropriate base directory for task workspaces."""
    if "SENTINEL_RUNS_DIR" in os.environ:
        return os.path.abspath(os.environ["SENTINEL_RUNS_DIR"])
    if os.name == "nt":
        return os.path.abspath(os.path.join(tempfile.gettempdir(), "sentinel-runs"))
    return "/tmp/sentinel-runs"


def create_task_workspace(
    repo_path: str,
    base_commit: str,
    task_id: str,
    runs_dir: str | None = None,
) -> str:
    """
    Create a fresh git worktree at {runs_dir}/{task_id}/workspace checked out at base_commit.
    Returns the absolute path to the workspace root.
    Guarantees the original repo at repo_path is never mutated.
    """
    repo_real = os.path.realpath(repo_path)
    if not os.path.exists(repo_real):
        raise ValueError(f"Repository path does not exist: {repo_path}")

    # Verify repo_path is actually a git repository
    try:
        res = subprocess.run(
            ["git", "-C", repo_real, "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=True,
        )
        if res.stdout.strip() != "true":
            raise ValueError(f"Not a valid git repository: {repo_path}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise ValueError(f"Failed to verify git repository at {repo_path}: {e}")

    # Verify base_commit exists
    try:
        subprocess.run(
            ["git", "-C", repo_real, "rev-parse", "--verify", f"{base_commit}^{{commit}}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        raise ValueError(f"Commit '{base_commit}' does not exist in repository {repo_path}")

    base_runs = runs_dir or get_default_runs_dir()
    workspace_path = os.path.abspath(os.path.join(base_runs, task_id, "workspace"))

    # Ensure parent folder exists
    os.makedirs(os.path.dirname(workspace_path), exist_ok=True)

    if os.path.exists(workspace_path):
        # Clean up stale workspace before recreation
        try:
            subprocess.run(
                ["git", "-C", repo_real, "worktree", "remove", "--force", workspace_path],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            pass
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path, ignore_errors=True)

    # Add git worktree detached at base_commit
    cmd = ["git", "-C", repo_real, "worktree", "add", "--detach", workspace_path, base_commit]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git worktree add failed: {e.stderr.strip()}")

    return os.path.realpath(workspace_path)


def destroy_task_workspace(
    task_id: str,
    runs_dir: str | None = None,
    repo_path: str | None = None,
) -> None:
    """
    Remove the git worktree and clean up disk state for the given task_id.
    """
    base_runs = runs_dir or get_default_runs_dir()
    task_dir = os.path.abspath(os.path.join(base_runs, task_id))
    workspace_path = os.path.join(task_dir, "workspace")

    if repo_path and os.path.exists(repo_path):
        subprocess.run(
            ["git", "-C", repo_path, "worktree", "remove", "--force", workspace_path],
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(
            ["git", "-C", repo_path, "worktree", "prune"],
            capture_output=True,
            text=True,
            check=False,
        )

    # Force remove directory if git worktree remove left remnants or repo_path was not supplied
    if os.path.exists(task_dir):
        # On Windows, git files might be read-only, handle onerror
        def _remove_readonly(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)

        shutil.rmtree(task_dir, onerror=_remove_readonly)
