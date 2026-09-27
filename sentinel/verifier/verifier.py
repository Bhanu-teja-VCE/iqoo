"""
Deterministic Verifier for Sentinel.
Executes test suites in the sandbox and verifies actual on-disk git diffs.
The core engine that stops agents from falsely claiming success.
"""

import time
from typing import Any

from sentinel.sandbox.tools import run_tests
from sentinel.verifier.diff_analyzer import get_workspace_diff, validate_diff


def verify_task(
    workspace_path: str,
    test_command: str,
    expected_files: list[str] | None = None,
    base_commit: str = "HEAD",
    allow_empty_diff: bool = False,
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Deterministically verify an agent's task completion.
    1. Inspects the actual git diff inside the workspace.
    2. Validates that the diff is non-empty (if fix required) and within file boundaries.
    3. Runs the real test command inside the sandbox.
    4. Combines test pass/fail with diff validity to yield absolute truth.

    Returns structured verification result matching TaskState schema.
    """
    start_time = time.perf_counter()

    # 1. Inspect on-disk git diff
    diff_info = get_workspace_diff(workspace_path, base_commit=base_commit)
    diff_valid, diff_reason = validate_diff(
        diff_info,
        expected_files=expected_files,
        allow_empty=allow_empty_diff,
    )

    # 2. Run real test suite inside sandbox
    test_res = run_tests(test_command, workspace_path, timeout=timeout)
    test_data = test_res.get("result", {})
    exit_code = test_data.get("exit_code", -1)
    timed_out = test_data.get("timed_out", False)
    test_passed = (exit_code == 0) and not timed_out

    # 3. Formulate deterministic verdict
    overall_passed = test_passed and diff_valid

    if timed_out:
        detail = f"Verification FAILED: Test command '{test_command}' timed out after {timeout}s."
    elif not test_passed:
        detail = (
            f"Verification FAILED: Test command '{test_command}' exited with code {exit_code}.\n"
            f"Output snippet:\n{test_data.get('stderr') or test_data.get('stdout') or 'No output'}"
        )
    elif not diff_valid:
        detail = f"Verification FAILED (Tests passed, but diff invalid): {diff_reason}"
    else:
        files = diff_info.get("files_changed", [])
        detail = (
            f"Verification PASSED: All tests passed (exit 0) and valid diff confirmed "
            f"({len(files)} file(s) modified: {files})."
        )

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    return {
        "passed": overall_passed,
        "detail": detail,
        "diff": diff_info.get("raw_diff", ""),
        "files_changed": diff_info.get("files_changed", []),
        "insertions": diff_info.get("insertions", 0),
        "deletions": diff_info.get("deletions", 0),
        "test_exit_code": exit_code,
        "test_stdout": test_data.get("stdout", ""),
        "test_stderr": test_data.get("stderr", ""),
        "timed_out": timed_out,
        "duration_ms": duration_ms,
    }
