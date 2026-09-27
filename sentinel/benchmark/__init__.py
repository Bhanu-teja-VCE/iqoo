"""
Sentinel Benchmark Package.
"""

from sentinel.benchmark.runner import (
    run_comparative_benchmark,
    run_single_eval,
    setup_task_repository,
)
from sentinel.benchmark.scorecard import (
    compute_metrics,
    export_scorecard_json,
    render_scorecard_table,
)
from sentinel.benchmark.tasks import (
    BENCHMARK_TASKS,
    BenchmarkTask,
)

__all__ = [
    "BenchmarkTask",
    "BENCHMARK_TASKS",
    "setup_task_repository",
    "run_single_eval",
    "run_comparative_benchmark",
    "compute_metrics",
    "render_scorecard_table",
    "export_scorecard_json",
]
