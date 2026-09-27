"""
Diff Analyzer for Sentinel Verifier.
Extracts and validates true on-disk git diffs from task workspaces.
Never trusts an agent's self-reported changes.
"""

import os
import subprocess
from typing import Any


IGNORE_SUBSTRINGS = ("__pycache__", ".pytest_cache", ".coverage", ".git")
IGNORE_EXTENSIONS = (".pyc", ".pyo", ".pyd")


def is_cache_artifact(filepath: str) -> bool:
    """Detect Python cache, bytecode, and test runner artifacts."""
    norm = filepath.replace("\\", "/").lower()
    if any(pat in norm for pat in IGNORE_SUBSTRINGS):
        return True
    if norm.endswith(IGNORE_EXTENSIONS):
        return True
    return False


def get_workspace_diff(workspace_path: str, base_commit: str = "HEAD") -> dict[str, Any]:
    """
    Extract the real git diff from the workspace against base_commit.
    Captures both tracked modifications and newly created (untracked) files.
    """
    ws_real = os.path.realpath(workspace_path)
    if not os.path.isdir(ws_real):
        return {
            "raw_diff": "",
            "files_changed": [],
            "insertions": 0,
            "deletions": 0,
            "error": f"Workspace directory does not exist: {workspace_path}",
        }

    try:
        # Mark untracked files with intent-to-add so git diff includes them
        subprocess.run(
            ["git", "-C", ws_real, "add", "-N", "."],
            capture_output=True,
            check=False,
        )

        # Extract full diff text against base_commit
        diff_proc = subprocess.run(
            ["git", "-C", ws_real, "diff", base_commit],
            capture_output=True,
            text=True,
            check=False,
        )
        raw_diff = diff_proc.stdout

        # Extract list of changed file names
        name_proc = subprocess.run(
            ["git", "-C", ws_real, "diff", "--name-only", base_commit],
            capture_output=True,
            text=True,
            check=False,
        )
        raw_files = [line.strip() for line in name_proc.stdout.splitlines() if line.strip()]
        files_changed = [f for f in raw_files if not is_cache_artifact(f)]

        # Extract shortstat (e.g. " 1 file changed, 2 insertions(+), 1 deletion(-)")
        stat_proc = subprocess.run(
            ["git", "-C", ws_real, "diff", "--shortstat", base_commit],
            capture_output=True,
            text=True,
            check=False,
        )
        stat_text = stat_proc.stdout.strip()

        insertions = 0
        deletions = 0
        if stat_text:
            parts = stat_text.split(",")
            for p in parts:
                p_clean = p.strip()
                if "insertion" in p_clean:
                    insertions = int(p_clean.split()[0])
                elif "deletion" in p_clean:
                    deletions = int(p_clean.split()[0])

        return {
            "raw_diff": raw_diff,
            "files_changed": files_changed,
            "insertions": insertions,
            "deletions": deletions,
            "error": None,
        }

    except Exception as e:
        return {
            "raw_diff": "",
            "files_changed": [],
            "insertions": 0,
            "deletions": 0,
            "error": f"Failed to compute diff: {e}",
        }


def validate_diff(
    diff_info: dict[str, Any],
    expected_files: list[str] | None = None,
    allow_empty: bool = False,
) -> tuple[bool, str]:
    """
    Validate diff properties against task expectations.
    1. Rejects empty diffs if changes were expected.
    2. Rejects diffs modifying files outside expected_files boundary.
    Returns (valid: bool, reason: str).
    """
    if diff_info.get("error"):
        return False, f"Diff extraction error: {diff_info['error']}"

    files_changed = [f for f in diff_info.get("files_changed", []) if not is_cache_artifact(f)]

    if not allow_empty and not files_changed:
        return False, "Agent claimed completion, but zero files were modified in the repository."

    if expected_files is not None:
        # Normalize paths for platform independence
        norm_expected = {os.path.normpath(f).lower() for f in expected_files}
        norm_changed = {os.path.normpath(f).lower() for f in files_changed}

        unexpected = norm_changed - norm_expected
        if unexpected:
            return (
                False,
                f"Diff modified unauthorized or unexpected files outside boundary: {sorted(unexpected)}",
            )

    return True, f"Diff is valid ({len(files_changed)} file(s) modified)."
