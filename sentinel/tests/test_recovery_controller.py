"""
Tests for Sentinel Recovery Controller.
Verifies bounded retries, circuit breaker tripping, escalation, and replanning.
"""

import unittest

from sentinel.core.recovery import (
    RecoveryAction,
    RecoveryController,
)
from sentinel.core.types import TaskState


class TestRecoveryController(unittest.TestCase):
    def setUp(self):
        self.controller = RecoveryController(max_attempts=3, allow_escalation=True)

    def test_circuit_breaker_trips_at_max_attempts(self):
        """When attempt_count reaches max_attempts, controller must abort with ABORT_FAIL."""
        state = TaskState(
            task_id="task-circuit-breaker",
            workspace_path="/tmp/ws",
            instruction="Fix network socket error",
            attempt_count=3,  # Already at limit
            verifier_result={"passed": False, "detail": "Test failed with exit code 1"},
            status="verifying",
        )

        action, rationale = self.controller.evaluate(state)
        self.assertEqual(action, RecoveryAction.ABORT_FAIL)
        self.assertIn("circuit breaker", rationale.lower())

        # Apply recovery and assert status becomes failed
        updated = self.controller.apply_recovery(state, action, rationale)
        self.assertEqual(updated.status, "failed")

    def test_escalate_to_frontier_on_final_local_attempt(self):
        """When local model reaches max_attempts - 1, controller escalates to frontier model."""
        state = TaskState(
            task_id="task-escalation",
            workspace_path="/tmp/ws",
            instruction="Fix recursive parser bug",
            attempt_count=2,  # Final attempt before abort (3 - 1 = 2)
            model_used="local",
            verifier_result={"passed": False, "detail": "RecursionError: maximum depth exceeded"},
        )

        action, rationale = self.controller.evaluate(state)
        self.assertEqual(action, RecoveryAction.ESCALATE)
        self.assertIn("escalat", rationale.lower())

        # Apply recovery and assert model_used switches to frontier
        updated = self.controller.apply_recovery(state, action, rationale)
        self.assertEqual(updated.model_used, "frontier")
        self.assertEqual(updated.status, "recovering")
        self.assertEqual(updated.attempt_count, 3)

    def test_replan_on_boundary_or_zero_diff_violation(self):
        """Structural failures trigger REPLAN and insert diagnostic step into plan."""
        state = TaskState(
            task_id="task-replan",
            workspace_path="/tmp/ws",
            instruction="Refactor auth service",
            plan=["Step 1: Edit auth.py", "Step 2: Run tests"],
            current_step_index=0,
            attempt_count=0,
            verifier_result={"passed": False, "detail": "Diff modified unauthorized or unexpected files: ['secrets.json']"},
        )

        action, rationale = self.controller.evaluate(state)
        self.assertEqual(action, RecoveryAction.REPLAN)

        # Apply recovery and assert diagnostic step is inserted into plan
        initial_plan_len = len(state.plan)
        updated = self.controller.apply_recovery(state, action, rationale)
        self.assertEqual(len(updated.plan), initial_plan_len + 1)
        self.assertIn("Analyze failure diagnostics", updated.plan[1])

    def test_retry_on_syntax_or_test_failure(self):
        """Code and test failures trigger RETRY with feedback."""
        state = TaskState(
            task_id="task-retry",
            workspace_path="/tmp/ws",
            instruction="Fix calculation bug",
            attempt_count=0,
            verifier_result={"passed": False, "detail": "SyntaxError: invalid syntax at line 14"},
        )

        action, rationale = self.controller.evaluate(state)
        self.assertEqual(action, RecoveryAction.RETRY)
        self.assertIn("syntax", rationale.lower())

        updated = self.controller.apply_recovery(state, action, rationale)
        self.assertEqual(updated.status, "recovering")
        self.assertEqual(updated.attempt_count, 1)


if __name__ == "__main__":
    unittest.main()
