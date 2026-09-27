"""
Tests for TaskState Schema and Checkpoint Store.
Verifies serialization, atomic snapshotting, chronological listing, and rollback.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from sentinel.core.checkpoint import (
    get_git_history,
    get_latest_checkpoint,
    git_commit_step,
    list_checkpoints,
    load_checkpoint,
    rollback_to_checkpoint,
    save_checkpoint,
)
from sentinel.core.types import TaskState


class TestStateAndCheckpoint(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_ckpt_")
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.repo_dir, exist_ok=True)

        # Initialize git repo in repo_dir for rollback testing
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "CkptTester"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "tester@ckpt.local"], cwd=self.repo_dir, capture_output=True, check=True)

        with open(os.path.join(self.repo_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write("print('clean baseline')\n")

        subprocess.run(["git", "add", "."], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Baseline commit"], cwd=self.repo_dir, capture_output=True, check=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_task_state_serialization_roundtrip(self):
        """TaskState must serialize to JSON and deserialize back identically."""
        original = TaskState(
            task_id="task-test-01",
            workspace_path="/tmp/test",
            instruction="Fix auth token bug",
            plan=["Step 1: Read file", "Step 2: Propose fix"],
            current_step_index=1,
            attempt_count=1,
            injected_fault="truncated_diff",
            status="executing",
            model_used="local",
        )

        json_data = original.to_json()
        restored = TaskState.from_json(json_data)

        self.assertEqual(original.task_id, restored.task_id)
        self.assertEqual(original.plan, restored.plan)
        self.assertEqual(original.current_step_index, restored.current_step_index)
        self.assertEqual(original.attempt_count, restored.attempt_count)
        self.assertEqual(original.injected_fault, restored.injected_fault)
        self.assertEqual(original.model_used, restored.model_used)

    def test_checkpoint_save_and_load_roundtrip(self):
        """save_checkpoint and load_checkpoint must persist and restore from disk."""
        state = TaskState(
            task_id="task-ckpt-roundtrip",
            workspace_path=self.repo_dir,
            instruction="Optimize sorting function",
            plan=["Step 1", "Step 2"],
            current_step_index=0,
            attempt_count=0,
        )

        ckpt_id = save_checkpoint(state, checkpoint_dir=self.checkpoint_dir)
        self.assertIn("step_000_attempt_0", ckpt_id)

        loaded = load_checkpoint("task-ckpt-roundtrip", ckpt_id, checkpoint_dir=self.checkpoint_dir)
        self.assertEqual(loaded.task_id, state.task_id)
        self.assertEqual(loaded.instruction, state.instruction)
        self.assertEqual(loaded.checkpoint_id, ckpt_id)

    def test_checkpoint_listing_and_latest(self):
        """list_checkpoints and get_latest_checkpoint must follow step progression."""
        state = TaskState(
            task_id="task-multi-ckpt",
            workspace_path=self.repo_dir,
            instruction="Multi-step task",
        )

        # Step 0
        state.current_step_index = 0
        save_checkpoint(state, checkpoint_dir=self.checkpoint_dir)

        # Step 1
        state.current_step_index = 1
        save_checkpoint(state, checkpoint_dir=self.checkpoint_dir)

        # Step 2
        state.current_step_index = 2
        save_checkpoint(state, checkpoint_dir=self.checkpoint_dir)

        ckpts = list_checkpoints("task-multi-ckpt", checkpoint_dir=self.checkpoint_dir)
        self.assertEqual(len(ckpts), 3)

        latest = get_latest_checkpoint("task-multi-ckpt", checkpoint_dir=self.checkpoint_dir)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.current_step_index, 2)

    def test_rollback_reverts_state_and_workspace(self):
        """rollback_to_checkpoint must restore prior TaskState and discard dirty disk edits."""
        state = TaskState(
            task_id="task-rollback",
            workspace_path=self.repo_dir,
            instruction="Fix database connector",
            current_step_index=0,
            attempt_count=0,
        )
        good_ckpt_id = save_checkpoint(state, checkpoint_dir=self.checkpoint_dir)

        # Simulate agent making bad edits and dirty untracked files
        with open(os.path.join(self.repo_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write("corrupted code def broken(((\n")
        with open(os.path.join(self.repo_dir, "bad_untracked.py"), "w", encoding="utf-8") as f:
            f.write("junk\n")

        # Mutate state in memory
        state.current_step_index = 1
        state.attempt_count = 1

        # Perform rollback to good checkpoint
        restored = rollback_to_checkpoint(
            state,
            good_ckpt_id,
            checkpoint_dir=self.checkpoint_dir,
            revert_git_workspace=True,
        )

        # Verify state is restored
        self.assertEqual(restored.current_step_index, 0)
        self.assertEqual(restored.attempt_count, 0)

        # Verify filesystem was restored: main.py clean, bad_untracked.py purged
        with open(os.path.join(self.repo_dir, "main.py"), "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("clean baseline", content)
        self.assertFalse(os.path.exists(os.path.join(self.repo_dir, "bad_untracked.py")))

    def test_git_commit_and_history_tracking(self):
        """git_commit_step must create verifiable commits and get_git_history must parse them."""
        # 1. Modify a file and commit
        with open(os.path.join(self.repo_dir, "feature.py"), "w", encoding="utf-8") as f:
            f.write("def feature(): return 42\n")

        sha1 = git_commit_step(self.repo_dir, "[sentinel] Added feature.py | step 1")
        self.assertIsNotNone(sha1)
        self.assertEqual(len(sha1), 40)

        # 2. Make an empty status commit
        sha2 = git_commit_step(self.repo_dir, "[sentinel] Verifier PASSED", allow_empty=True)
        self.assertIsNotNone(sha2)

        # 3. Retrieve history
        history = get_git_history(self.repo_dir)
        self.assertGreaterEqual(len(history), 3)  # initial commit + 2 sentinel commits
        self.assertIn("[sentinel] Verifier PASSED", history[0]["message"])
        self.assertIn("[sentinel] Added feature.py", history[1]["message"])
        self.assertEqual(history[0]["sha"], sha2)
        self.assertEqual(history[1]["sha"], sha1)


if __name__ == "__main__":
    unittest.main()
