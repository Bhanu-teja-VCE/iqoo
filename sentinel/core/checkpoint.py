"""
Checkpoint Store for Sentinel.
Writes atomic JSON snapshots of TaskState to disk after every step.
Enables instant kill-and-resume and clean state rollback on failure.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sentinel.core.types import TaskState


def get_default_checkpoint_dir() -> str:
    """Return platform-appropriate base directory for checkpoints."""
    if "SENTINEL_CHECKPOINT_DIR" in os.environ:
        return os.path.abspath(os.environ["SENTINEL_CHECKPOINT_DIR"])
    return os.path.abspath(os.path.join(tempfile.gettempdir(), "sentinel-checkpoints"))


def save_checkpoint(state: TaskState, checkpoint_dir: str | None = None) -> str:
    """
    Save TaskState to a structured JSON snapshot file.
    Path: {checkpoint_dir}/{task_id}/{step_index}_{attempt_count}.json
    Returns the checkpoint_id.
    """
    base_dir = checkpoint_dir or get_default_checkpoint_dir()
    task_dir = os.path.join(base_dir, state.task_id)
    os.makedirs(task_dir, exist_ok=True)

    checkpoint_id = f"step_{state.current_step_index:03d}_attempt_{state.attempt_count}"
    state.checkpoint_id = checkpoint_id

    file_path = os.path.join(task_dir, f"{checkpoint_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(state.to_json())

    return checkpoint_id


def load_checkpoint(
    task_id: str,
    checkpoint_id: str,
    checkpoint_dir: str | None = None,
) -> TaskState:
    """
    Load and reconstruct TaskState from a specific checkpoint ID.
    """
    base_dir = checkpoint_dir or get_default_checkpoint_dir()
    file_path = os.path.join(base_dir, task_id, f"{checkpoint_id}.json")

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Checkpoint '{checkpoint_id}' not found for task '{task_id}' at {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return TaskState.from_json(content)


def list_checkpoints(task_id: str, checkpoint_dir: str | None = None) -> list[str]:
    """
    List all available checkpoint IDs for a task in chronological order.
    """
    base_dir = checkpoint_dir or get_default_checkpoint_dir()
    task_dir = os.path.join(base_dir, task_id)

    if not os.path.isdir(task_dir):
        return []

    files = [f for f in os.listdir(task_dir) if f.endswith(".json")]
    files.sort()
    return [f[:-5] for f in files]


def get_latest_checkpoint(task_id: str, checkpoint_dir: str | None = None) -> TaskState | None:
    """
    Retrieve the most recent TaskState checkpoint for a task.
    """
    checkpoints = list_checkpoints(task_id, checkpoint_dir=checkpoint_dir)
    if not checkpoints:
        return None
    latest_id = checkpoints[-1]
    return load_checkpoint(task_id, latest_id, checkpoint_dir=checkpoint_dir)


def rollback_to_checkpoint(
    state: TaskState,
    checkpoint_id: str,
    checkpoint_dir: str | None = None,
    revert_git_workspace: bool = True,
) -> TaskState:
    """
    Roll back state to a previous checkpoint.
    Optionally discards dirty worktree changes so retries start from a clean slate.
    """
    restored_state = load_checkpoint(state.task_id, checkpoint_id, checkpoint_dir=checkpoint_dir)

    if revert_git_workspace and os.path.isdir(restored_state.workspace_path):
        try:
            # Revert any uncommitted changes in the worktree
            subprocess.run(
                ["git", "-C", restored_state.workspace_path, "checkout", "--", "."],
                capture_output=True,
                check=False,
            )
            # Remove untracked new files created during the failed step
            subprocess.run(
                ["git", "-C", restored_state.workspace_path, "clean", "-fd"],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass

    return restored_state


def git_commit_step(
    workspace_path: str,
    message: str,
    allow_empty: bool = True,
) -> str | None:
    """
    Create a git commit in the workspace to record the current state.
    Builds a visible audit trail: every tool call, verification, and recovery
    becomes a commit you can walk through with `git log`.

    Returns the commit SHA, or None if the commit failed.
    """
    if not os.path.isdir(workspace_path):
        return None

    try:
        # Stage all changes (including new files)
        subprocess.run(
            ["git", "-C", workspace_path, "add", "-A"],
            capture_output=True,
            check=False,
        )

        # Build commit command
        cmd = ["git", "-C", workspace_path, "commit", "-m", message]
        if allow_empty:
            cmd.append("--allow-empty")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return None

        # Get the commit SHA
        sha_result = subprocess.run(
            ["git", "-C", workspace_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return sha_result.stdout.strip() if sha_result.returncode == 0 else None

    except Exception:
        return None


def get_git_history(
    workspace_path: str,
    max_count: int = 50,
) -> list[dict[str, str]]:
    """
    Retrieve the git commit history from the workspace.
    Returns a list of dicts: {sha, short_sha, message, timestamp, diff_stat}.
    """
    if not os.path.isdir(workspace_path):
        return []

    try:
        # Get log with custom format: SHA|short_sha|timestamp|message
        result = subprocess.run(
            [
                "git", "-C", workspace_path, "log",
                f"--max-count={max_count}",
                "--format=%H|%h|%aI|%s",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue

            sha, short_sha, timestamp, message = parts

            # Get diffstat for each commit (files changed, insertions, deletions)
            stat_result = subprocess.run(
                [
                    "git", "-C", workspace_path, "diff",
                    "--shortstat", f"{sha}~1", sha,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            diff_stat = stat_result.stdout.strip() if stat_result.returncode == 0 else ""

            commits.append({
                "sha": sha,
                "short_sha": short_sha,
                "timestamp": timestamp,
                "message": message,
                "diff_stat": diff_stat,
            })

        return commits

    except Exception:
        return []

