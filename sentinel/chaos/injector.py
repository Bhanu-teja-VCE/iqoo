"""
Failure Injector Engine for Sentinel.
Applies deterministic, seeded chaos faults to tool calls and files during evaluation runs.
Enables quantifying agent resilience and self-recovery.
"""

import random
import time
from typing import Any

from sentinel.chaos.faults import FaultClass


class FailureInjector:
    """
    Deterministic failure injection engine.
    Uses a fixed random seed so that evaluation benchmarks are 100% reproducible.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.fault_log: list[dict[str, Any]] = []

    def reset(self, seed: int | None = None) -> None:
        """Reset the injector and optionally update the random seed."""
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed)
        self.fault_log.clear()

    def inject_write_fault(
        self,
        content: str,
        fault: str | FaultClass,
    ) -> tuple[str, str]:
        """
        Deterministically corrupts file content before writing to disk.
        Returns (corrupted_content, description).
        """
        fault_val = fault.value.lower() if hasattr(fault, "value") else str(fault).lower()

        if fault_val in (FaultClass.TRUNCATED_DIFF.value, "truncated_diff"):
            lines = content.splitlines(keepends=True)
            if len(lines) <= 2:
                # If short, truncate characters by half
                cut_idx = max(1, len(content) // 2)
                corrupted = content[:cut_idx]
            else:
                # Keep first 50% of lines
                cut_line = max(1, int(len(lines) * 0.5))
                corrupted = "".join(lines[:cut_line])

            desc = f"Simulated context cutoff: truncated file at {len(corrupted)} bytes ({len(lines)} lines -> truncated)."
            self._log_event(FaultClass.TRUNCATED_DIFF.value, desc)
            return corrupted, desc

        elif fault_val in (FaultClass.SYNTAX_CORRUPT.value, "syntax_corrupt"):
            corrupted = "class _SyntaxCorruptedToken(((: # CHAOS INJECTED SYNTAX ERROR\n" + content
            desc = "Injected unclosed syntax token at top of file."
            self._log_event(FaultClass.SYNTAX_CORRUPT.value, desc)
            return corrupted, desc

        elif fault_val in (FaultClass.NONE.value, "none"):
            return content, "No write fault applied."

        return content, f"Unknown write fault class '{fault}'; content unchanged."

    def inject_execution_fault(
        self,
        cmd: list[str],
        timeout: int,
        fault: str | FaultClass,
    ) -> tuple[list[str], int, str]:
        """
        Deterministically alters command or timeout limits before subprocess execution.
        Returns (modified_cmd, modified_timeout, description).
        """
        fault_val = fault.value.lower() if hasattr(fault, "value") else str(fault).lower()

        if fault_val in (FaultClass.TOOL_TIMEOUT.value, "tool_timeout"):
            # Force timeout to 1 second and inject a sleep command to trigger timeout
            desc = "Injected 5-second sleep and forced 1-second timeout to trigger watchdog."
            self._log_event(FaultClass.TOOL_TIMEOUT.value, desc)
            sleep_cmd = ["python3", "-c", "import time; time.sleep(5)"]
            return sleep_cmd, 1, desc

        elif fault_val in (FaultClass.FLAKY_TEST.value, "flaky_test"):
            # Inject failing assertion into python test command
            desc = "Injected deliberate exit code 1 to simulate flaky test failure."
            self._log_event(FaultClass.FLAKY_TEST.value, desc)
            failing_cmd = ["python3", "-c", "import sys; print('CHAOS INJECTED FLAKY FAILURE', file=sys.stderr); sys.exit(1)"]
            return failing_cmd, timeout, desc

        return cmd, timeout, "No execution fault applied."

    def _log_event(self, fault_type: str, detail: str) -> None:
        self.fault_log.append({
            "timestamp": time.time(),
            "fault": fault_type,
            "detail": detail,
        })
