"""
Tests for Sentinel Append-Only Trace Logger.
Verifies JSONL event emission, timestamping, and parsing.
"""

import os
import shutil
import tempfile
import unittest

from sentinel.core.trace import (
    TraceLogger,
    read_task_trace,
)


class TestTraceLogger(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_trace_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_log_and_read_events(self):
        task_id = "task-trace-01"
        logger = TraceLogger(task_id=task_id, traces_dir=self.test_dir)

        # Log sequential events
        logger.log("task_started", {"instruction": "Fix bug", "model": "local"})
        logger.log("plan_created", {"plan": ["step 1", "step 2"]})
        logger.log("tool_called", {"tool": "write_file", "path": "auth.py"})
        logger.log("verifier_ran", {"passed": False, "detail": "Test failed"})
        logger.log("recovery_triggered", {"action": "retry", "attempt": 1})
        logger.log("task_finished", {"status": "done"})

        # Verify trace file exists on disk
        trace_path = os.path.join(self.test_dir, f"{task_id}.jsonl")
        self.assertTrue(os.path.isfile(trace_path))

        # Read events
        events = read_task_trace(task_id, traces_dir=self.test_dir)
        self.assertEqual(len(events), 6)

        self.assertEqual(events[0]["event_type"], "task_started")
        self.assertEqual(events[0]["data"]["instruction"], "Fix bug")
        self.assertGreater(events[0]["timestamp"], 0)

        self.assertEqual(events[3]["event_type"], "verifier_ran")
        self.assertFalse(events[3]["data"]["passed"])

        self.assertEqual(events[-1]["event_type"], "task_finished")
        self.assertEqual(events[-1]["data"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
