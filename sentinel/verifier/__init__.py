"""
Sentinel Verifier Package.
Deterministic test execution and diff verification.
"""

from sentinel.verifier.diff_analyzer import (
    get_workspace_diff,
    validate_diff,
)
from sentinel.verifier.verifier import verify_task

__all__ = [
    "verify_task",
    "get_workspace_diff",
    "validate_diff",
]
