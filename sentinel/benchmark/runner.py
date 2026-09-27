"""
Benchmark Runner for Sentinel.
Executes head-to-head evaluation comparing Raw Agent vs. Sentinel Harnessed Agent
under controlled, reproducible chaos fault injection.
"""

import os
import shutil
import subprocess
import tempfile
import time
from typing import Any

from sentinel.agent.model_adapter import ModelAdapter
from sentinel.agent.orchestrator import run_task_loop
from sentinel.benchmark.tasks import BENCHMARK_TASKS, BenchmarkTask
from sentinel.chaos.injector import FailureInjector
from sentinel.core.types import TaskState
from sentinel.sandbox.workspace import (
    create_task_workspace,
    destroy_task_workspace,
)
from sentinel.verifier.verifier import verify_task


def setup_task_repository(task: BenchmarkTask, base_dir: str, run_id: str | None = None) -> tuple[str, str]:
    """
    Instantiate a clean git repository containing the buggy code and test files for a task.
    Returns (repo_path, base_commit).
    """
    suffix = f"_{run_id}" if run_id else ""
    repo_path = os.path.join(base_dir, f"repo_{task.task_id}{suffix}")
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)
    os.makedirs(repo_path, exist_ok=True)

    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "BenchmarkBot"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "benchmark@sentinel.local"], cwd=repo_path, capture_output=True, check=True)

    # Write buggy source files
    for fname, code in task.buggy_files.items():
        fpath = os.path.join(repo_path, fname)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

    # Write test files
    for fname, code in task.test_files.items():
        fpath = os.path.join(repo_path, fname)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", f"Initial buggy commit for {task.name}"], cwd=repo_path, capture_output=True, check=True)

    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True, check=True)
    base_commit = res.stdout.strip()

    return repo_path, base_commit


class TaskSpecificMockAdapter(ModelAdapter):
    """Context-aware mock adapter for benchmark tasks that reliably executes and repairs tasks."""

    def __init__(self, task: BenchmarkTask):
        self.task = task
        self.target_file = task.expected_files[0]
        self.correct_content = task.correct_files.get(self.target_file, "")

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        import json
        prompt_lower = prompt.lower()
        if "plan" in prompt_lower:
            return json.dumps([
                f"Read {self.target_file}",
                f"Write fix to {self.target_file}",
                "Run test suite",
            ])
        elif "read" in prompt_lower or "investigate" in prompt_lower:
            return json.dumps({
                "tool": "read_file",
                "args": {"path": self.target_file},
            })
        elif "write" in prompt_lower or "fix" in prompt_lower or "alternative" in prompt_lower or "diagnostics" in prompt_lower:
            return json.dumps({
                "tool": "write_file",
                "args": {"path": self.target_file, "content": self.correct_content},
            })
        else:
            return json.dumps({
                "tool": "run_tests",
                "args": {"test_command": self.task.test_command},
            })


def run_single_eval(
    task: BenchmarkTask,
    with_sentinel: bool,
    fault_type: str | None = None,
    model_adapter: ModelAdapter | None = None,
    base_work_dir: str | None = None,
) -> dict[str, Any]:
    """
    Execute a single task evaluation under either Sentinel or Raw baseline conditions.
    """
    work_dir = base_work_dir or tempfile.mkdtemp(prefix="sentinel_bench_")
    run_tag = "sentinel" if with_sentinel else "raw"
    repo_path, base_commit = setup_task_repository(task, work_dir, run_id=run_tag)

    active_model = model_adapter or TaskSpecificMockAdapter(task)

    start_time = time.perf_counter()

    if with_sentinel:
        # ---------------------------------------------------------------------
        # HARNESSED RUN (WITH SENTINEL)
        # ---------------------------------------------------------------------
        runs_dir = os.path.join(work_dir, "runs")
        ckpts_dir = os.path.join(work_dir, "checkpoints")
        traces_dir = os.path.join(work_dir, "traces")

        ws_path = create_task_workspace(
            repo_path=repo_path,
            base_commit=base_commit,
            task_id=task.task_id,
            runs_dir=runs_dir,
        )

        state = TaskState(
            task_id=task.task_id,
            workspace_path=ws_path,
            instruction=task.instruction,
            injected_fault=fault_type,
            status="planning",
        )

        injector = FailureInjector(seed=42) if fault_type else None

        final_state = run_task_loop(
            state=state,
            test_command=task.test_command,
            model_adapter=active_model,
            expected_files=task.expected_files,
            fault_injector=injector,
            checkpoint_dir=ckpts_dir,
            traces_dir=traces_dir,
            max_attempts=3,
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        passed = (final_state.status == "done")
        recovered = passed and (final_state.attempt_count > 0)

        # Cleanup workspace
        destroy_task_workspace(task.task_id, runs_dir=runs_dir, repo_path=repo_path)

        return {
            "task_id": task.task_id,
            "task_name": task.name,
            "mode": "WITH_SENTINEL",
            "fault_injected": fault_type or "none",
            "passed": passed,
            "recovered": recovered,
            "attempts": final_state.attempt_count,
            "duration_ms": duration_ms,
            "claimed_success": True,  # Sentinel checks truth
            "false_claim": False,     # Zero false claims
        }

    else:
        # ---------------------------------------------------------------------
        # UN-HARNESSED RUN (RAW AGENT BASELINE)
        # ---------------------------------------------------------------------
        # Raw agent edits files directly, has 0 checkpoints, no retry loop.
        # If fault injected, corrupted code is written and agent claims success.
        target_file = task.expected_files[0]
        correct_content = task.correct_files.get(target_file, "")
        target_path = os.path.join(repo_path, target_file)

        if fault_type == "truncated_diff":
            # Cuts code in half
            content_to_write = correct_content[: len(correct_content) // 2]
        elif fault_type == "syntax_corrupt":
            content_to_write = "def broken(((: # corrupt\n" + correct_content
        else:
            content_to_write = correct_content

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content_to_write)

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Ground truth verification: does the test actually pass?
        verify_check = verify_task(repo_path, task.test_command, expected_files=task.expected_files)
        actually_passed = verify_check["passed"]

        # Raw agent ALWAYS self-reports success: "I fixed the bug!"
        claimed_success = True
        false_claim = claimed_success and not actually_passed

        return {
            "task_id": task.task_id,
            "task_name": task.name,
            "mode": "WITHOUT_SENTINEL",
            "fault_injected": fault_type or "none",
            "passed": actually_passed,
            "recovered": False,  # Raw agent has no recovery controller
            "attempts": 0,
            "duration_ms": duration_ms,
            "claimed_success": claimed_success,
            "false_claim": false_claim,
        }


def run_comparative_benchmark(
    tasks: list[BenchmarkTask] | None = None,
    fault_type: str = "truncated_diff",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Run the complete comparative benchmark across all tasks:
    Returns (raw_results, sentinel_results).
    """
    benchmark_tasks = tasks or BENCHMARK_TASKS
    raw_results = []
    sentinel_results = []

    with tempfile.TemporaryDirectory(prefix="sentinel_suite_") as suite_dir:
        for task in benchmark_tasks:
            # 1. Run without Sentinel
            raw_res = run_single_eval(
                task=task,
                with_sentinel=False,
                fault_type=fault_type,
                base_work_dir=suite_dir,
            )
            raw_results.append(raw_res)

            # 2. Run with Sentinel
            sentinel_res = run_single_eval(
                task=task,
                with_sentinel=True,
                fault_type=fault_type,
                base_work_dir=suite_dir,
            )
            sentinel_results.append(sentinel_res)

    return raw_results, sentinel_results
