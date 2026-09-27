"""
Fault definitions and categories for Sentinel Chaos Injection.
Used to evaluate agent detection and recovery capabilities.
"""

from enum import Enum


class FaultClass(str, Enum):
    """Supported fault injection classes."""
    NONE = "none"
    TRUNCATED_DIFF = "truncated_diff"      # Simulates model token limit / cut-off patch
    SYNTAX_CORRUPT = "syntax_corrupt"      # Injects unparseable syntax error
    TOOL_TIMEOUT = "tool_timeout"          # Forces tool execution watchdog timeout
    FLAKY_TEST = "flaky_test"              # Injects transient environment/test failure
