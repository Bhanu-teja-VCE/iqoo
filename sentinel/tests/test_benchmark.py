"""
Tests for Sentinel Benchmark Suite and Scorecard.
Verifies repository setup, evaluation runs, metrics computation, and report rendering.
"""

import os
import shutil
import tempfile
import unittest

from sentinel.benchmark.runner import (
    run_single_eval,
    setup_task_repository,
)
from sentinel.benchmark.scorecard import (
    compute_metrics,
    render_scorecard_table,
)
from sentinel.benchmark.tasks import BENCHMARK_TASKS


class TestBenchmark(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_test_bench_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_setup_task_repository(self):
        """setup_task_repository must initialize git repo and commit initial files."""
        task = BENCHMARK_TASKS[0]
        repo_path, commit = setup_task_repository(task, self.test_dir)

        self.assertTrue(os.path.isdir(repo_path))
        self.assertEqual(len(commit), 40)  # Valid 40-char git commit hash
        self.assertTrue(os.path.isfile(os.path.join(repo_path, "auth.py")))
        self.assertTrue(os.path.isfile(os.path.join(repo_path, "test_auth.py")))

    def test_compute_metrics(self):
        """compute_metrics must accurately calculate percentages and rates."""
        sample_results = [
            {"passed": True, "recovered": True, "false_claim": False, "duration_ms": 100},
            {"passed": True, "recovered": False, "false_claim": False, "duration_ms": 120},
            {"passed": False, "recovered": False, "false_claim": True, "duration_ms": 80},
            {"passed": False, "recovered": False, "false_claim": False, "duration_ms": 100},
        ]

        metrics = compute_metrics(sample_results)
        self.assertEqual(metrics["total_tasks"], 4)
        self.assertEqual(metrics["passed_count"], 2)
        self.assertEqual(metrics["success_rate_pct"], 50.0)
        self.assertEqual(metrics["recovery_rate_pct"], 25.0)
        self.assertEqual(metrics["false_claims_pct"], 25.0)

    def test_render_scorecard_table(self):
        """render_scorecard_table must output formatted table with headers."""
        raw_res = [{"passed": False, "recovered": False, "false_claim": True, "duration_ms": 50}]
        sent_res = [{"passed": True, "recovered": True, "false_claim": False, "duration_ms": 150}]

        table = render_scorecard_table(raw_res, sent_res, fault_type="truncated_diff")
        self.assertIn("SENTINEL RELIABILITY SCORECARD", table)
        self.assertIn("Task Success Rate", table)
        self.assertIn("Automatic Self-Recovery Rate", table)

    def test_run_single_eval_with_and_without_sentinel(self):
        """run_single_eval must run both modes and return expected schema."""
        task = BENCHMARK_TASKS[0]

        # 1. Un-harnessed (Raw) run under fault injection -> fails with false claim
        raw_eval = run_single_eval(
            task=task,
            with_sentinel=False,
            fault_type="truncated_diff",
            base_work_dir=self.test_dir,
        )
        self.assertFalse(raw_eval["passed"])
        self.assertTrue(raw_eval["false_claim"])
        self.assertEqual(raw_eval["mode"], "WITHOUT_SENTINEL")

        # 2. Harnessed (Sentinel) run under fault injection -> recovers and passes
        sent_eval = run_single_eval(
            task=task,
            with_sentinel=True,
            fault_type="truncated_diff",
            base_work_dir=self.test_dir,
        )
        self.assertTrue(sent_eval["passed"])
        self.assertFalse(sent_eval["false_claim"])
        self.assertEqual(sent_eval["mode"], "WITH_SENTINEL")


if __name__ == "__main__":
    unittest.main()
