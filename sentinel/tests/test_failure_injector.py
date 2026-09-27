"""
Tests for Sentinel Failure Injector.
Verifies deterministic, reproducible chaos fault injection across all fault classes.
"""

import ast
import unittest

from sentinel.chaos.faults import FaultClass
from sentinel.chaos.injector import FailureInjector
from sentinel.sandbox.executor_sandbox import run_in_sandbox


class TestFailureInjector(unittest.TestCase):
    def setUp(self):
        self.injector = FailureInjector(seed=1337)
        self.sample_code = (
            "def authenticate(username, token):\n"
            "    if not username or not token:\n"
            "        return False\n"
            "    hashed = hash(token)\n"
            "    return True\n"
        )

    def test_truncated_diff_injection(self):
        """TRUNCATED_DIFF must cut code short, simulating token context cutoff."""
        corrupted, desc = self.injector.inject_write_fault(
            self.sample_code,
            FaultClass.TRUNCATED_DIFF,
        )

        self.assertLess(len(corrupted), len(self.sample_code))
        self.assertIn("truncated", desc.lower())
        # Truncated python function will be incomplete and invalid
        with self.assertRaises(SyntaxError):
            ast.parse(corrupted)

    def test_syntax_corrupt_injection(self):
        """SYNTAX_CORRUPT must inject malformed syntax that fails ast.parse."""
        corrupted, desc = self.injector.inject_write_fault(
            self.sample_code,
            FaultClass.SYNTAX_CORRUPT,
        )

        self.assertIn("SyntaxCorruptedToken", corrupted)
        self.assertIn("syntax", desc.lower())
        with self.assertRaises(SyntaxError):
            ast.parse(corrupted)

    def test_tool_timeout_injection(self):
        """TOOL_TIMEOUT alters timeout and injects sleep, triggering watchdog."""
        cmd = ["python3", "-c", "print('fast')"]
        mod_cmd, mod_timeout, desc = self.injector.inject_execution_fault(
            cmd,
            timeout=30,
            fault=FaultClass.TOOL_TIMEOUT,
        )

        self.assertEqual(mod_timeout, 1)
        self.assertIn("sleep", str(mod_cmd))

        # Run modified command in temporary sandbox and verify it times out
        import tempfile
        with tempfile.TemporaryDirectory() as temp_ws:
            res = run_in_sandbox(mod_cmd, temp_ws, timeout=mod_timeout)
            self.assertTrue(res.get("timed_out"))
            self.assertEqual(res.get("exit_code"), -1)

    def test_flaky_test_injection(self):
        """FLAKY_TEST injects deliberate failure exit code into command."""
        cmd = ["python3", "-c", "print('all good')"]
        mod_cmd, mod_timeout, desc = self.injector.inject_execution_fault(
            cmd,
            timeout=30,
            fault=FaultClass.FLAKY_TEST,
        )

        import tempfile
        with tempfile.TemporaryDirectory() as temp_ws:
            res = run_in_sandbox(mod_cmd, temp_ws, timeout=mod_timeout)
            self.assertEqual(res.get("exit_code"), 1)
            self.assertIn("CHAOS INJECTED FLAKY FAILURE", res.get("stderr"))

    def test_deterministic_reproducibility(self):
        """Two injectors with the same seed produce identical behavior."""
        inj1 = FailureInjector(seed=999)
        inj2 = FailureInjector(seed=999)

        c1, _ = inj1.inject_write_fault(self.sample_code, FaultClass.TRUNCATED_DIFF)
        c2, _ = inj2.inject_write_fault(self.sample_code, FaultClass.TRUNCATED_DIFF)

        self.assertEqual(c1, c2)

    def test_fault_logging(self):
        """All injected faults must be recorded in fault_log for evaluation metrics."""
        self.injector.inject_write_fault(self.sample_code, FaultClass.SYNTAX_CORRUPT)
        self.assertEqual(len(self.injector.fault_log), 1)
        self.assertEqual(self.injector.fault_log[0]["fault"], "syntax_corrupt")


if __name__ == "__main__":
    unittest.main()
