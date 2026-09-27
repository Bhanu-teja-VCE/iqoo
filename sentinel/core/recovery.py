"""
Recovery Controller for Sentinel.
Pure deterministic decision logic that evaluates failures, bounds retries,
and prevents infinite loops.
"""

from enum import Enum
from typing import Any

from sentinel.core.types import TaskState


class RecoveryAction(str, Enum):
    """Actions decided by the Recovery Controller."""
    RETRY = "retry"            # Re-execute step with error diagnostics injected
    REPLAN = "replan"          # Insert diagnostic or alternative step into plan
    ESCALATE = "escalate"      # Switch model from local to frontier
    ABORT_FAIL = "abort_fail"  # Circuit breaker tripped; halt execution


class RecoveryController:
    """
    Deterministic resilience engine.
    Bounds retries, analyzes verifier failure traces, and decides recovery paths.
    """

    def __init__(self, max_attempts: int = 3, allow_escalation: bool = True):
        self.max_attempts = max_attempts
        self.allow_escalation = allow_escalation

    def evaluate(self, state: TaskState) -> tuple[RecoveryAction, str]:
        """
        Evaluate the current task failure and decide the appropriate recovery action.
        Returns (action, rationale).
        """
        # 1. Circuit breaker: Hard bound on retries
        if state.attempt_count >= self.max_attempts:
            return (
                RecoveryAction.ABORT_FAIL,
                f"Circuit breaker tripped: reached max attempts ({self.max_attempts}). "
                "Halting loop to prevent infinite token consumption.",
            )

        detail = ""
        if state.verifier_result:
            detail = state.verifier_result.get("detail", "").lower()

        # 2. Escalation path: If local model has struggled and we are on final attempt
        if (
            self.allow_escalation
            and state.model_used == "local"
            and state.attempt_count == self.max_attempts - 1
        ):
            return (
                RecoveryAction.ESCALATE,
                f"Local model retries exhausted (attempt {state.attempt_count}). "
                "Escalating task to frontier model for final resolution.",
            )

        # 3. Structural or boundary violations -> Replan
        if any(keyword in detail for keyword in ("unauthorized", "unexpected files", "zero files", "escapes workspace")):
            return (
                RecoveryAction.REPLAN,
                "Structural or boundary failure detected. Inserting replan step to inspect file paths and scope.",
            )

        # 4. Syntax / compile / truncation error -> Retry with syntax diagnostics
        if any(keyword in detail for keyword in ("syntax", "truncated", "syntaxerror")):
            return (
                RecoveryAction.RETRY,
                f"Syntax or truncation error detected (attempt {state.attempt_count + 1}/{self.max_attempts}). "
                "Retrying step with syntax diagnostics injected into prompt context.",
            )

        # 5. General test execution failure -> Retry with feedback
        if any(keyword in detail for keyword in ("exit code", "failed")):
            return (
                RecoveryAction.RETRY,
                f"Test failure detected (attempt {state.attempt_count + 1}/{self.max_attempts}). "
                "Retrying step with test failure feedback injected into prompt context.",
            )

        # Default fallback action
        return (
            RecoveryAction.RETRY,
            f"Retrying step with verifier feedback (attempt {state.attempt_count + 1}/{self.max_attempts}).",
        )

    def apply_recovery(
        self,
        state: TaskState,
        action: RecoveryAction,
        rationale: str,
    ) -> TaskState:
        """
        Apply the decided recovery action to TaskState.
        Updates counters, status, and execution plan deterministically.
        """
        if action == RecoveryAction.ABORT_FAIL:
            state.status = "failed"
            return state

        state.attempt_count += 1

        if action == RecoveryAction.ESCALATE:
            state.model_used = "frontier"
            state.status = "recovering"

        elif action == RecoveryAction.REPLAN:
            state.status = "recovering"
            insert_idx = state.current_step_index + 1
            replan_step = f"Analyze failure diagnostics and formulate alternative approach: {rationale}"
            state.plan.insert(insert_idx, replan_step)

        elif action == RecoveryAction.RETRY:
            state.status = "recovering"

        return state
