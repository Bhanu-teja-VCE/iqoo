"""
Generic Agent-Loop Evaluator for Sentinel.

Evaluates ANY existing agent loop passed in as input — not just Sentinel's
own planner/executor — by running it against isolated task repos and scoring
with the deterministic verifier (pytest exit + git diff).

An "agent loop" here is any callable with signature:
    agent_fn(task: BenchmarkTask, workspace_path: str) -> dict
that writes/ edits files inside workspace_path and returns
{"claimed_success": bool, "notes": str}.

Preset behaviours are provided so the frontend can demo without code upload,
plus a `custom_files` path that lets a user paste their agent's exact output.
To plug a real loop (Aider / SWE-agent / in-house), register it:
    from sentinel.benchmark.agent_eval import register_agent_loop
    register_agent_loop("my_agent", my_fn)
then POST /api/evaluate with {"agent_name": "my_agent"}.
"""

import os
import tempfile
import time
from collections.abc import Callable
from typing import Any

from sentinel.benchmark.scorecard import compute_metrics
from sentinel.benchmark.tasks import BENCHMARK_TASKS, BenchmarkTask
from sentinel.verifier.verifier import verify_task

# Agent function type: (task, workspace_path) -> {"claimed_success": bool, "notes": str}
AgentFn = Callable[[BenchmarkTask, str], dict[str, Any]]

AGENT_REGISTRY: dict[str, AgentFn] = {}


def register_agent_loop(name: str, fn: AgentFn) -> None:
    """Register a real agent loop callable under `name`."""
    AGENT_REGISTRY[name] = fn


def _write_files(workspace_path: str, files: dict[str, str]) -> None:
    for fname, content in files.items():
        fpath = os.path.join(workspace_path, fname)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)


def _preset_correct(task: BenchmarkTask, workspace_path: str) -> dict[str, Any]:
    _write_files(workspace_path, task.correct_files)
    return {"claimed_success": True, "notes": "wrote correct fix"}


def _preset_truncated(task: BenchmarkTask, workspace_path: str) -> dict[str, Any]:
    target = task.expected_files[0]
    full = task.correct_files.get(target, "")
    _write_files(workspace_path, {target: full[: len(full) // 2]})
    return {"claimed_success": True, "notes": "simulated context cutoff (50% truncated)"}


def _preset_empty(task: BenchmarkTask, workspace_path: str) -> dict[str, Any]:
    # Writes nothing — tests zero-diff rejection.
    return {"claimed_success": True, "notes": "wrote nothing (zero-diff)"}


def _preset_wrong_file(task: BenchmarkTask, workspace_path: str) -> dict[str, Any]:
    _write_files(workspace_path, {"wrong_place.py": "x = 1\n"})
    return {"claimed_success": True, "notes": "edited file outside expected boundary"}


def _preset_syntax_corrupt(task: BenchmarkTask, workspace_path: str) -> dict[str, Any]:
    target = task.expected_files[0]
    full = task.correct_files.get(target, "")
    _write_files(workspace_path, {target: "class _SyntaxCorruptedToken(((: # CHAOS\n" + full})
    return {"claimed_success": True, "notes": "injected syntax corruption"}


register_agent_loop("correct", _preset_correct)
register_agent_loop("truncated", _preset_truncated)
register_agent_loop("empty", _preset_empty)
register_agent_loop("wrong_file", _preset_wrong_file)
register_agent_loop("syntax_corrupt", _preset_syntax_corrupt)


def list_preset_agents() -> list[dict[str, str]]:
    return [
        {"name": "correct", "label": "Correct agent (writes ground-truth fix)"},
        {"name": "truncated", "label": "Truncated agent (50% cutoff — simulates small-model overflow)"},
        {"name": "empty", "label": "Empty agent (claims success, changes nothing)"},
        {"name": "wrong_file", "label": "Wrong-file agent (edits outside boundary)"},
        {"name": "syntax_corrupt", "label": "Syntax-corrupt agent (unparseable output)"},
        {"name": "custom", "label": "Custom — paste your agent's file outputs as JSON"},
    ]


def evaluate_agent_loop(
    agent_name: str,
    tasks: list[BenchmarkTask] | None = None,
    custom_files_by_task: dict[str, dict[str, str]] | None = None,
    base_work_dir: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Run one agent loop across tasks. Returns (per_task_results, metrics).
    Each result: {task_id, task_name, passed, claimed_success, false_claim, detail, ...}
    Metrics: same shape as scorecard.compute_metrics + false_claims_pct.
    """
    from sentinel.benchmark.runner import setup_task_repository

    targets = tasks or BENCHMARK_TASKS
    work_dir = base_work_dir or tempfile.mkdtemp(prefix="sentinel_agent_eval_")
    results: list[dict[str, Any]] = []

    # Resolve agent fn (custom handled per-task below)
    agent_fn = AGENT_REGISTRY.get(agent_name) if agent_name != "custom" else None
    if agent_name != "custom" and agent_fn is None:
        raise ValueError(f"Unknown agent '{agent_name}'. Registered: {sorted(AGENT_REGISTRY)}")

    import tempfile as _tf
    with _tf.TemporaryDirectory(prefix="sentinel_agent_suite_") as suite_dir:
        # Use caller work_dir as parent when supplied for traceability; suite_dir for isolation.
        parent = base_work_dir or suite_dir
        for task in targets:
            repo_path, _ = setup_task_repository(task, parent, run_id=f"eval_{agent_name}")
            start = time.perf_counter()
            claimed = True
            notes = ""
            try:
                if agent_name == "custom":
                    files = (custom_files_by_task or {}).get(task.task_id, {})
                    _write_files(repo_path, files)
                    notes = f"custom pasted output ({len(files)} file(s))"
                else:
                    assert agent_fn is not None
                    out = agent_fn(task, repo_path)
                    claimed = bool(out.get("claimed_success", True))
                    notes = str(out.get("notes", ""))
            except Exception as e:
                claimed = True
                notes = f"agent crashed: {e}"

            duration_ms = int((time.perf_counter() - start) * 1000)
            # Ground-truth verification — never trusts agent self-report.
            v = verify_task(repo_path, task.test_command, expected_files=task.expected_files)
            passed = bool(v["passed"])
            results.append({
                "task_id": task.task_id,
                "task_name": task.name,
                "agent": agent_name,
                "passed": passed,
                "claimed_success": claimed,
                "false_claim": bool(claimed and not passed),
                "recovered": False,  # single-shot eval; recovery is Sentinel-harness property
                "notes": notes,
                "detail": v["detail"],
                "files_changed": v["files_changed"],
                "test_exit_code": v["test_exit_code"],
                "duration_ms": duration_ms,
            })

    metrics = compute_metrics(results)
    return results, metrics
