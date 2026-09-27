"""
Execution Sandbox Layer for Sentinel.
Enforces command whitelist, resource limits, and environment sanitization.
Provides Docker container execution with a documented host subprocess fallback.
"""

import logging
import os
import shlex
import shutil
import subprocess
import sys
from typing import Any

from sentinel.sandbox.exceptions import ToolExecutionError

logger = logging.getLogger("sentinel.sandbox")

# Strict whitelist: Only these commands are allowed as the first executable token
ALLOWED_COMMANDS = {"pytest", "python3", "ls", "cat", "grep"}

# Safe environment variables permitted in fallback subprocess execution
SAFE_ENV_VARS = {
    "PATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
    "PYTHONPATH",
    "LANG",
    "LC_ALL",
    "TERM",
}

# Prefix and exact matches for variables that must ALWAYS be stripped
SENSITIVE_ENV_PREFIXES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
    "AWS_",
    "GITHUB_",
    "GH_",
    "OPENAI_",
    "ANTHROPIC_",
    "SSH_",
    "AZURE_",
    "GCP_",
    "GOOGLE_",
    "TOKEN",
    "SECRET",
    "KEY",
    "PASSWORD",
    "CREDENTIAL",
)


def is_docker_available() -> bool:
    """
    Detect whether Docker is installed and the Docker daemon is actively responding.
    Returns True only if 'docker info' succeeds.
    """
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=3,
            check=False,
        )
        return res.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _sanitized_env() -> dict[str, str]:
    """
    Build a clean environment dictionary for subprocess execution:
    - Strips proxies, network-altering vars, cloud credentials, and secret tokens.
    - Preserves minimal operating system and runtime variables.
    - On Windows, ensures Git/usr/bin is in PATH if available for POSIX tool support.
    """
    clean_env: dict[str, str] = {}
    for k, v in os.environ.items():
        k_upper = k.upper()
        # Drop any sensitive keys
        if any(k_upper.startswith(prefix) or prefix in k_upper for prefix in SENSITIVE_ENV_PREFIXES):
            continue
        # Drop proxy keys
        if "PROXY" in k_upper:
            continue
        if k in SAFE_ENV_VARS or k_upper in SAFE_ENV_VARS:
            clean_env[k] = v

    # Fallback PATH if none preserved
    if "PATH" not in clean_env:
        clean_env["PATH"] = os.environ.get("PATH", "")

    # Windows helper: include Git/usr/bin if ls/cat/grep are not found natively
    if os.name == "nt":
        git_usr_bin = r"C:\Program Files\Git\usr\bin"
        if os.path.isdir(git_usr_bin) and git_usr_bin not in clean_env["PATH"]:
            clean_env["PATH"] = f"{git_usr_bin};{clean_env['PATH']}"

    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    return clean_env


def _set_resource_limits():
    """
    Set CPU time and address space limits for child processes on POSIX systems.
    No-op on platforms without the Unix resource module (e.g. Windows).
    """
    try:
        import resource
        # 30s CPU time limit
        resource.setrlimit(resource.RLIMIT_CPU, (30, 35))
        # 512MB address space limit
        mem_bytes = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ImportError, ValueError, OSError):
        pass


def _normalize_host_command(cmd: list[str]) -> list[str]:
    """
    Normalize command tokens for host execution.
    For example on Windows, if 'python3' is passed and only 'python' or sys.executable is functional,
    route to sys.executable.
    """
    normalized = list(cmd)
    if normalized and normalized[0] == "python3":
        if os.name == "nt":
            # Check if python3 actually works or if it's the Windows Store stub
            p3 = shutil.which("python3")
            if not p3 or "WindowsApps" in p3:
                normalized[0] = sys.executable
    return normalized


def run_in_sandbox(
    cmd: list[str],
    workspace_path: str,
    timeout: int = 30,
    docker_image: str = "python:3.11-slim",
) -> dict[str, Any]:
    """
    Execute a command inside the sandbox.
    1. Validates command against ALLOWED_COMMANDS whitelist before doing anything.
    2. Runs inside an isolated Docker container if Docker is available.
    3. Otherwise falls back to host subprocess with sanitized env and timeout, logging a clear warning.

    Returns dict:
        {"stdout": str, "stderr": str, "exit_code": int, "timed_out": bool}
    """
    if not cmd or not cmd[0]:
        raise ToolExecutionError("Command cannot be empty")

    first_token = cmd[0]
    if first_token not in ALLOWED_COMMANDS:
        raise ToolExecutionError(f"Command '{first_token}' is not permitted by whitelist. Allowed: {sorted(ALLOWED_COMMANDS)}")

    workspace_real = os.path.realpath(workspace_path)
    if not os.path.isdir(workspace_real):
        raise ToolExecutionError(f"Workspace directory does not exist: {workspace_path}")

    # 1. Docker execution path
    if is_docker_available():
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory=512m",
            "--cpus=1",
            "-v",
            f"{workspace_real}:/workspace:rw",
            "-w",
            "/workspace",
            docker_image,
        ] + cmd

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return {
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "stdout": (e.stdout or "").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                "stderr": "Execution timed out in container sandbox.",
                "exit_code": -1,
                "timed_out": True,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Docker execution error: {e}",
                "exit_code": -1,
                "timed_out": False,
            }

    # 2. Host subprocess fallback path
    logger.warning(
        "[FALLBACK WARNING] Docker is unavailable. Executing in host subprocess fallback "
        "with weaker isolation (no container namespace or network jail). Workspace: %s",
        workspace_real,
    )
    if os.name == "nt":
        logger.warning(
            "[FALLBACK WARNING] POSIX resource.setrlimit is unavailable on Windows. "
            "Execution is constrained by timeout (%ds) and sanitized environment.",
            timeout,
        )

    preexec = _set_resource_limits if sys.platform != "win32" else None
    env = _sanitized_env()
    host_cmd = _normalize_host_command(cmd)

    try:
        res = subprocess.run(
            host_cmd,
            cwd=workspace_real,
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=preexec,
            env=env,
            check=False,
        )
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as e:
        stdout_text = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode() if e.stdout else "")
        stderr_text = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode() if e.stderr else "")
        return {
            "stdout": stdout_text,
            "stderr": (stderr_text + "\nCommand timed out and was killed.").strip(),
            "exit_code": -1,
            "timed_out": True,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Subprocess execution error: {e}",
            "exit_code": -1,
            "timed_out": False,
        }
