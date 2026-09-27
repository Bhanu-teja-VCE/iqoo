"""
Tool API for Sentinel.
The only interface future Planner/Executor agents will ever call.
All filesystem and execution calls are validated strictly in code.
"""

import os
import shlex
from typing import Any

from sentinel.sandbox.exceptions import SandboxViolation, ToolExecutionError
from sentinel.sandbox.executor_sandbox import run_in_sandbox


def _resolve_in_workspace(path: str, workspace_path: str) -> str:
    """
    Resolve path relative to workspace_path and verify it does not escape.
    Raises SandboxViolation if path resolves outside workspace_path.
    Blocks '../../' traversal, absolute paths outside workspace, and symlink escapes.
    """
    if not path or not path.strip():
        raise SandboxViolation("Path cannot be empty")

    ws_real = os.path.realpath(workspace_path)

    # If already absolute, verify it sits inside ws_real; otherwise join with ws_real
    if os.path.isabs(path):
        target_real = os.path.realpath(path)
    else:
        target_real = os.path.realpath(os.path.join(ws_real, path))

    try:
        common = os.path.commonpath([target_real, ws_real])
    except ValueError:
        # On Windows, happens when drives differ (e.g. C: vs D:)
        raise SandboxViolation(f"Path '{path}' escapes workspace (different drive or root)")

    if common != ws_real:
        raise SandboxViolation(
            f"Path '{path}' escapes workspace (resolves to '{target_real}', root is '{ws_real}')"
        )

    return target_real


def read_file(path: str, workspace_path: str) -> dict[str, Any]:
    """
    Read file content from within the isolated workspace.
    Returns structured result dictionary.
    """
    target = _resolve_in_workspace(path, workspace_path)

    if not os.path.exists(target):
        return {
            "tool": "read_file",
            "args": {"path": path},
            "result": {},
            "error": f"File '{path}' does not exist",
        }

    if os.path.isdir(target):
        return {
            "tool": "read_file",
            "args": {"path": path},
            "result": {},
            "error": f"Path '{path}' is a directory, not a file",
        }

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {
            "tool": "read_file",
            "args": {"path": path},
            "result": {"content": content, "size_bytes": len(content)},
            "error": None,
        }
    except Exception as e:
        return {
            "tool": "read_file",
            "args": {"path": path},
            "result": {},
            "error": f"Failed to read file: {e}",
        }


def write_file(path: str, content: str, workspace_path: str) -> dict[str, Any]:
    """
    Write file content to a path within the isolated workspace.
    Creates parent directories if necessary.
    Returns structured result dictionary.
    """
    target = _resolve_in_workspace(path, workspace_path)

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "tool": "write_file",
            "args": {"path": path, "bytes_written": len(content)},
            "result": {"written": target, "bytes": len(content)},
            "error": None,
        }
    except Exception as e:
        return {
            "tool": "write_file",
            "args": {"path": path, "bytes_written": len(content)},
            "result": {},
            "error": f"Failed to write file: {e}",
        }


def run_shell(cmd: str, workspace_path: str, timeout: int = 30) -> dict[str, Any]:
    """
    Execute a shell command inside the sandbox.
    Tokenizes cmd with shlex, validates whitelist, and runs in sandbox.
    Returns structured result dictionary.
    """
    _resolve_in_workspace(".", workspace_path)

    try:
        tokens = shlex.split(cmd)
    except ValueError as e:
        return {
            "tool": "run_shell",
            "args": {"cmd": cmd, "timeout": timeout},
            "result": {},
            "error": f"Failed to parse shell command: {e}",
        }

    if not tokens:
        raise ToolExecutionError("Shell command cannot be empty")

    sandbox_res = run_in_sandbox(tokens, workspace_path, timeout=timeout)
    err = None
    if sandbox_res.get("timed_out"):
        err = "Command timed out"
    elif sandbox_res.get("exit_code") != 0:
        err = f"Command exited with status {sandbox_res.get('exit_code')}"

    return {
        "tool": "run_shell",
        "args": {"cmd": cmd, "timeout": timeout},
        "result": sandbox_res,
        "error": err,
    }


def run_tests(test_command: str, workspace_path: str, timeout: int = 60) -> dict[str, Any]:
    """
    Thin wrapper over run_shell for running test suites during verification.
    Returns structured result dictionary.
    """
    res = run_shell(test_command, workspace_path, timeout=timeout)
    return {
        "tool": "run_tests",
        "args": {"test_command": test_command, "timeout": timeout},
        "result": res["result"],
        "error": res["error"],
    }
