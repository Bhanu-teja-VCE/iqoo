"""
Tests for Sentinel Master Orchestrator.
Verifies the full end-to-end autonomous loop:
planning -> executing -> verifying -> recovery -> done/failed.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from sentinel.agent.model_adapter import MockModelAdapter
from sentinel.agent.orchestrator import run_task_loop
from sentinel.chaos.injector import FailureInjector
from sentinel.core.types import TaskState
from sentinel.sandbox.workspace import (
    create_task_workspace,
    destroy_task_workspace,
)


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_orch_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        self.runs_dir = os.path.join(self.test_dir, "runs")
        self.ckpts_dir = os.path.join(self.test_dir, "checkpoints")
        self.traces_dir = os.path.join(self.test_dir, "traces")

        os.makedirs(self.repo_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)
        os.makedirs(self.ckpts_dir, exist_ok=True)
        os.makedirs(self.traces_dir, exist_ok=True)

        # Initialize fixture git repo with failing test
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "OrchTester"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "tester@orch.local"], cwd=self.repo_dir, capture_output=True, check=True)

        buggy_code = "def is_active():\n    return False\n"
        test_code = (
            "import unittest\n"
            "from app import is_active\n"
            "class AppTest(unittest.TestCase):\n"
            "    def test_active(self):\n"
            "        self.assertTrue(is_active())\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

        with open(os.path.join(self.repo_dir, "app.py"), "w", encoding="utf-8") as f:
            f.write(buggy_code)
        with open(os.path.join(self.repo_dir, "test_app.py"), "w", encoding="utf-8") as f:
            f.write(test_code)

        subprocess.run(["git", "add", "."], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial buggy commit"], cwd=self.repo_dir, capture_output=True, check=True)

        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
        self.base_commit = res.stdout.strip()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_clean_end_to_end_pass(self):
        """Test clean autonomous task completion without faults."""
        task_id = "task-orch-clean"
        ws_path = create_task_workspace(
            repo_path=self.repo_dir,
            base_commit=self.base_commit,
            task_id=task_id,
            runs_dir=self.runs_dir,
        )

        # Scripted model that produces correct fix
        plan_response = json.dumps(["Investigate", "Write fix", "Verify"])
        read_response = json.dumps({"tool": "read_file", "args": {"path": "app.py"}})
        write_response = json.dumps({
            "tool": "write_file",
            "args": {"path": "app.py", "content": "def is_active():\n    return True\n"},
        })
        test_response = json.dumps({
            "tool": "run_tests",
            "args": {"test_command": "python3 test_app.py"},
        })

        mock_model = MockModelAdapter(scripted_responses=[
            plan_response,
            read_response,
            write_response,
            test_response,
        ])

        state = TaskState(
            task_id=task_id,
            workspace_path=ws_path,
            instruction="Fix is_active to return True",
            status="planning",
        )

        final_state = run_task_loop(
            state=state,
            test_command="python3 test_app.py",
            model_adapter=mock_model,
            expected_files=["app.py"],
            checkpoint_dir=self.ckpts_dir,
            traces_dir=self.traces_dir,
        )

        self.assertEqual(final_state.status, "done")
        self.assertIsNotNone(final_state.verifier_result)
        self.assertTrue(final_state.verifier_result["passed"])
        self.assertEqual(final_state.attempt_count, 0)

        destroy_task_workspace(task_id, runs_dir=self.runs_dir, repo_path=self.repo_dir)

    def test_end_to_end_recovery_under_chaos(self):
        """Test that injected fault causes verification failure, triggers rollback, and succeeds on retry."""
        task_id = "task-orch-recovery"
        ws_path = create_task_workspace(
            repo_path=self.repo_dir,
            base_commit=self.base_commit,
            task_id=task_id,
            runs_dir=self.runs_dir,
        )

        correct_write = json.dumps({
            "tool": "write_file",
            "args": {"path": "app.py", "content": "def is_active():\n    return True\n"},
        })

        # Responses: plan -> write (corrupted) -> retry write (clean)
        mock_model = MockModelAdapter(scripted_responses=[
            json.dumps(["Write fix"]),
            correct_write,  # First attempt will be corrupted by injector
            correct_write,  # Recovery retry attempt will succeed
        ])

        injector = FailureInjector(seed=42)

        state = TaskState(
            task_id=task_id,
            workspace_path=ws_path,
            instruction="Fix is_active to return True",
            injected_fault="truncated_diff",
            status="planning",
        )

        final_state = run_task_loop(
            state=state,
            test_command="python3 test_app.py",
            model_adapter=mock_model,
            expected_files=["app.py"],
            fault_injector=injector,
            checkpoint_dir=self.ckpts_dir,
            traces_dir=self.traces_dir,
            max_attempts=3,
        )

        self.assertEqual(final_state.status, "done")
        self.assertTrue(final_state.verifier_result["passed"])
        self.assertGreater(final_state.attempt_count, 0)

        destroy_task_workspace(task_id, runs_dir=self.runs_dir, repo_path=self.repo_dir)

    def test_circuit_breaker_halts_unrecoverable_task(self):
        """When an agent fails consistently, circuit breaker trips and halts loop."""
        task_id = "task-orch-fail"
        ws_path = create_task_workspace(
            repo_path=self.repo_dir,
            base_commit=self.base_commit,
            task_id=task_id,
            runs_dir=self.runs_dir,
        )

        # Model that keeps writing broken code
        broken_write = json.dumps({
            "tool": "write_file",
            "args": {"path": "app.py", "content": "def is_active():\n    return False # STILL BROKEN\n"},
        })
        mock_model = MockModelAdapter(scripted_responses=[
            json.dumps(["Write fix"]),
            broken_write,
            broken_write,
            broken_write,
        ])

        state = TaskState(
            task_id=task_id,
            workspace_path=ws_path,
            instruction="Fix bug",
            status="planning",
        )

        final_state = run_task_loop(
            state=state,
            test_command="python3 test_app.py",
            model_adapter=mock_model,
            expected_files=["app.py"],
            checkpoint_dir=self.ckpts_dir,
            traces_dir=self.traces_dir,
            max_attempts=2,  # Bound to 2 attempts
        )

        self.assertEqual(final_state.status, "failed")
        self.assertFalse(final_state.verifier_result["passed"])
        self.assertEqual(final_state.attempt_count, 2)

        destroy_task_workspace(task_id, runs_dir=self.runs_dir, repo_path=self.repo_dir)


if __name__ == "__main__":
    unittest.main()
