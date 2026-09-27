"""
Tests for Sandbox Isolation Layer.
Verifies path traversal protection, timeout termination, and fallback warning logging.
"""

import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sentinel.sandbox.exceptions import SandboxViolation
from sentinel.sandbox.executor_sandbox import run_in_sandbox
from sentinel.sandbox.tools import (
    _resolve_in_workspace,
    read_file,
    write_file,
)


class TestSandboxIsolation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_isolation_")
        self.workspace = os.path.join(self.test_dir, "workspace")
        self.outside_dir = os.path.join(self.test_dir, "outside")
        os.makedirs(self.workspace, exist_ok=True)
        os.makedirs(self.outside_dir, exist_ok=True)

        # Create sensitive decoy file outside workspace
        self.decoy_file = os.path.join(self.outside_dir, "decoy_secret.txt")
        with open(self.decoy_file, "w", encoding="utf-8") as f:
            f.write("SECRET_DATABASE_PASSWORD_DO_NOT_TOUCH")

        # Create normal file inside workspace
        self.inside_file = os.path.join(self.workspace, "hello.txt")
        with open(self.inside_file, "w", encoding="utf-8") as f:
            f.write("safe content inside workspace")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_relative_path_traversal_blocked(self):
        """Attempts to escape workspace using relative paths like ../../ must raise SandboxViolation."""
        bad_paths = [
            "../../outside/decoy_secret.txt",
            "../outside/decoy_secret.txt",
            "subdir/../../outside/decoy_secret.txt",
            "../../etc/passwd",
        ]
        for bad_path in bad_paths:
            with self.assertRaises(SandboxViolation, msg=f"Failed to block {bad_path}"):
                _resolve_in_workspace(bad_path, self.workspace)

            # Assert read_file raises SandboxViolation and decoy remains intact
            with self.assertRaises(SandboxViolation):
                read_file(bad_path, self.workspace)

            # Assert write_file raises SandboxViolation and decoy remains intact
            with self.assertRaises(SandboxViolation):
                write_file(bad_path, "MALICIOUS_OVERWRITE", self.workspace)

        # Verify decoy file outside was NEVER touched
        with open(self.decoy_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "SECRET_DATABASE_PASSWORD_DO_NOT_TOUCH")

    def test_absolute_path_outside_workspace_blocked(self):
        """Attempts to supply absolute paths outside workspace must raise SandboxViolation."""
        with self.assertRaises(SandboxViolation):
            _resolve_in_workspace(self.decoy_file, self.workspace)

        with self.assertRaises(SandboxViolation):
            read_file(self.decoy_file, self.workspace)

        with self.assertRaises(SandboxViolation):
            write_file(self.decoy_file, "OVERWRITE_ATTEMPT", self.workspace)

        # Ensure decoy is untouched
        with open(self.decoy_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "SECRET_DATABASE_PASSWORD_DO_NOT_TOUCH")

    def test_symlink_escape_blocked(self):
        """A symlink inside workspace pointing to a path outside must raise SandboxViolation."""
        symlink_target = self.decoy_file
        symlink_path = os.path.join(self.workspace, "symlink_to_outside.txt")

        try:
            os.symlink(symlink_target, symlink_path)
        except (OSError, NotImplementedError):
            # On Windows without developer mode/admin rights, symlink creation might be restricted
            self.skipTest("Symlink creation requires elevated privileges on this Windows environment")

        with self.assertRaises(SandboxViolation):
            _resolve_in_workspace("symlink_to_outside.txt", self.workspace)

        with self.assertRaises(SandboxViolation):
            read_file("symlink_to_outside.txt", self.workspace)

    def test_timeout_kills_runaway_command(self):
        """A command that exceeds timeout is terminated and returns timed_out: True."""
        # Using python3 sleep for 5 seconds with 1 second timeout
        cmd = ["python3", "-c", "import time; time.sleep(5)"]
        res = run_in_sandbox(cmd, self.workspace, timeout=1)

        self.assertTrue(res.get("timed_out"), "Expected command to time out")
        self.assertEqual(res.get("exit_code"), -1)
        self.assertIn("timed out", res.get("stderr", "").lower())

    def test_docker_unavailable_logs_fallback_warning(self):
        """When Docker is unavailable, the fallback path executes and logs a clear warning."""
        with patch("sentinel.sandbox.executor_sandbox.is_docker_available", return_value=False):
            with self.assertLogs("sentinel.sandbox", level=logging.WARNING) as cm:
                cmd = ["python3", "-c", "print('fallback executed')"]
                res = run_in_sandbox(cmd, self.workspace, timeout=10)

                self.assertFalse(res.get("timed_out"))
                self.assertIn("fallback executed", res.get("stdout", ""))
                # Assert fallback warning was logged
                warning_found = any("[FALLBACK WARNING]" in msg for msg in cm.output)
                self.assertTrue(warning_found, f"Expected [FALLBACK WARNING] in logs: {cm.output}")


if __name__ == "__main__":
    unittest.main()
