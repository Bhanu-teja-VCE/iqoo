"""
Tests for Sentinel Deterministic Verifier.
Verifies that diff analysis and real test execution determine true pass/fail outcomes.
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
from sentinel.verifier.diff_analyzer import get_workspace_diff, validate_diff
from sentinel.verifier.verifier import verify_task


class TestVerifier(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_verifier_")
        self.repo_dir = os.path.join(self.test_dir, "base_repo")
        self.runs_dir = os.path.join(self.test_dir, "runs")
        os.makedirs(self.repo_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "VerifierTester"], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "verifier@test.local"], cwd=self.repo_dir, capture_output=True, check=True)

        # Commit buggy code and test
        self.buggy_code = (
            "def calculate_tax(price):\n"
            "    # BUG: calculates wrong tax\n"
            "    return price * 0.5\n"
        )
        self.test_code = (
            "import unittest\n"
            "from math_module import calculate_tax\n\n"
            "class TaxTest(unittest.TestCase):\n"
            "    def test_tax(self):\n"
            "        self.assertEqual(calculate_tax(100), 10)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

        with open(os.path.join(self.repo_dir, "math_module.py"), "w", encoding="utf-8") as f:
            f.write(self.buggy_code)
        with open(os.path.join(self.repo_dir, "test_tax.py"), "w", encoding="utf-8") as f:
            f.write(self.test_code)

        subprocess.run(["git", "add", "."], cwd=self.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Buggy tax calculation commit"], cwd=self.repo_dir, capture_output=True, check=True)

        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_dir, capture_output=True, text=True, check=True)
        self.base_commit = res.stdout.strip()

        # Create worktree for test
        self.task_id = "task-verifier-test"
        self.workspace = create_task_workspace(
            repo_path=self.repo_dir,
            base_commit=self.base_commit,
            task_id=self.task_id,
            runs_dir=self.runs_dir,
        )

    def tearDown(self):
        destroy_task_workspace(task_id=self.task_id, runs_dir=self.runs_dir, repo_path=self.repo_dir)
        def _rm(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, onerror=_rm)

    def test_unfixed_code_fails_verification(self):
        """Before the bug is fixed, verify_task must report passed: False."""
        res = verify_task(
            workspace_path=self.workspace,
            test_command="python3 test_tax.py",
            expected_files=["math_module.py"],
            base_commit=self.base_commit,
        )
        self.assertFalse(res["passed"])
        self.assertNotEqual(res["test_exit_code"], 0)
        self.assertIn("Verification FAILED", res["detail"])

    def test_fixed_code_passes_verification(self):
        """When code is correctly fixed in the workspace, verify_task reports passed: True."""
        fixed_code = (
            "def calculate_tax(price):\n"
            "    # FIXED tax\n"
            "    return price * 0.10\n"
        )
        with open(os.path.join(self.workspace, "math_module.py"), "w", encoding="utf-8") as f:
            f.write(fixed_code)

        res = verify_task(
            workspace_path=self.workspace,
            test_command="python3 test_tax.py",
            expected_files=["math_module.py"],
            base_commit=self.base_commit,
        )

        self.assertTrue(res["passed"])
        self.assertEqual(res["test_exit_code"], 0)
        self.assertIn("math_module.py", res["files_changed"])
        self.assertGreater(res["insertions"], 0)
        self.assertIn("Verification PASSED", res["detail"])

    def test_zero_diff_hallucination_rejected(self):
        """If a dummy passing test runs but zero files were modified, verification fails."""
        res = verify_task(
            workspace_path=self.workspace,
            test_command='python3 -c "assert True"',
            expected_files=["math_module.py"],
            base_commit=self.base_commit,
            allow_empty_diff=False,
        )
        self.assertFalse(res["passed"])
        self.assertIn("zero files were modified", res["detail"])

    def test_unexpected_file_edit_rejected(self):
        """If an agent modifies files outside expected_files boundary, verification fails."""
        # Fix the bug in math_module
        fixed_code = "def calculate_tax(price):\n    return price * 0.10\n"
        with open(os.path.join(self.workspace, "math_module.py"), "w", encoding="utf-8") as f:
            f.write(fixed_code)

        # But also tamper with unauthorized file
        with open(os.path.join(self.workspace, "unauthorized.py"), "w", encoding="utf-8") as f:
            f.write("# unauthorized tampering\n")

        res = verify_task(
            workspace_path=self.workspace,
            test_command="python3 test_tax.py",
            expected_files=["math_module.py"],
            base_commit=self.base_commit,
        )

        self.assertFalse(res["passed"])
        self.assertIn("Diff modified unauthorized or unexpected files", res["detail"])


if __name__ == "__main__":
    unittest.main()
