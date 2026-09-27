"""
Tests for Workspace Isolation via git worktree.
Verifies clean creation, checkout, isolation, and destruction.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from sentinel.sandbox.workspace import (
    create_task_workspace,
    destroy_task_workspace,
)


class TestWorkspaceIsolation(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_ws_")
        self.repo_dir = os.path.join(self.test_dir, "base_repo")
        self.runs_dir = os.path.join(self.test_dir, "runs")
        os.makedirs(self.repo_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)

        # Initialize fixture git repo with one commit
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.name", "SentinelTester"],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "tester@sentinel.local"],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )

        initial_file = os.path.join(self.repo_dir, "README.md")
        with open(initial_file, "w", encoding="utf-8") as f:
            f.write("# Base Repository\nInitial commit for Sentinel test.\n")

        subprocess.run(["git", "add", "."], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )

        # Get initial commit hash
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        self.initial_commit = res.stdout.strip()

    def tearDown(self):
        # Clean up test directories
        def _force_rm(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, onerror=_force_rm)

    def test_create_and_destroy_workspace_roundtrip(self):
        task_id = "task-001"
        ws_path = create_task_workspace(
            repo_path=self.repo_dir,
            base_commit=self.initial_commit,
            task_id=task_id,
            runs_dir=self.runs_dir,
        )

        # Assert workspace exists and is inside runs_dir
        self.assertTrue(os.path.isdir(ws_path))
        self.assertIn(task_id, ws_path)

        # Assert initial file is present in workspace
        ws_readme = os.path.join(ws_path, "README.md")
        self.assertTrue(os.path.isfile(ws_readme))
        with open(ws_readme, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Initial commit for Sentinel test.", content)

        # Mutate workspace: add new file and modify README
        new_file = os.path.join(ws_path, "new_code.py")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("print('in workspace')\n")

        # Assert base repository is untouched
        base_new_file = os.path.join(self.repo_dir, "new_code.py")
        self.assertFalse(os.path.exists(base_new_file))

        # Destroy workspace
        destroy_task_workspace(task_id=task_id, runs_dir=self.runs_dir, repo_path=self.repo_dir)
        self.assertFalse(os.path.exists(ws_path))

    def test_invalid_repo_or_commit(self):
        # Invalid repo
        with self.assertRaises(ValueError):
            create_task_workspace(
                repo_path=os.path.join(self.test_dir, "nonexistent"),
                base_commit="HEAD",
                task_id="task-bad-repo",
                runs_dir=self.runs_dir,
            )

        # Invalid commit
        with self.assertRaises(ValueError):
            create_task_workspace(
                repo_path=self.repo_dir,
                base_commit="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                task_id="task-bad-commit",
                runs_dir=self.runs_dir,
            )


if __name__ == "__main__":
    unittest.main()
