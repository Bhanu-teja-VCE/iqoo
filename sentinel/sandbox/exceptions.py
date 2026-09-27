"""
Sentinel Sandbox Exceptions.
Code-enforced isolation and security boundaries.
"""


class SentinelError(Exception):
    """Base exception for all Sentinel errors."""
    pass


class SandboxViolation(SentinelError):
    """Raised when an operation attempts to escape or violate the workspace sandbox boundary."""
    pass


class ToolExecutionError(SentinelError):
    """Raised when a tool command violates the whitelist or fails pre-execution checks."""
    pass
