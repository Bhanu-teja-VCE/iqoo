"""
Master Orchestrator for Sentinel.
A deterministic Python state machine loop driving TaskState through:
planning -> executing -> verifying -> recovering -> done/failed.
"""

from typing import Any

from sentinel.agent.executor import execute_step
from sentinel.agent.model_adapter import ModelAdapter
from sentinel.agent.planner import generate_plan
from sentinel.chaos.injector import FailureInjector
from sentinel.core.checkpoint import (
    git_commit_step,
    rollback_to_checkpoint,
    save_checkpoint,
)
from sentinel.core.recovery import (
    RecoveryAction,
    RecoveryController,
)
from sentinel.core.trace import TraceLogger
from sentinel.core.types import TaskState
from sentinel.verifier.verifier import verify_task


def run_task_loop(
    state: TaskState,
    test_command: str,
    model_adapter: ModelAdapter,
    expected_files: list[str] | None = None,
    fault_injector: FailureInjector | None = None,
    checkpoint_dir: str | None = None,
    traces_dir: str | None = None,
    max_attempts: int = 3,
    max_loop_ticks: int = 30,
) -> TaskState:
    """
    Drive a task to completion through Sentinel's deterministic state machine.
    Never trusts model self-reports; all state transitions are guarded by Python logic.
    """
    logger = TraceLogger(task_id=state.task_id, traces_dir=traces_dir)
    recovery_controller = RecoveryController(max_attempts=max_attempts)

    logger.log("task_started", {
        "instruction": state.instruction,
        "workspace": state.workspace_path,
        "model": state.model_used,
        "fault": state.injected_fault,
    })

    # Track last good checkpoint before executing plan modifications
    last_good_checkpoint_id: str | None = None

    ticks = 0
    while state.status not in ("done", "failed") and ticks < max_loop_ticks:
        ticks += 1

        # ---------------------------------------------------------------------
        # 1. PLANNING STAGE
        # ---------------------------------------------------------------------
        if state.status == "planning":
            plan = generate_plan(state, model_adapter)
            logger.log("plan_created", {"plan": plan})
            state.status = "executing"
            state.current_step_index = 0
            last_good_checkpoint_id = save_checkpoint(state, checkpoint_dir=checkpoint_dir)
            logger.log("checkpoint_saved", {"checkpoint_id": last_good_checkpoint_id})
            git_commit_step(
                state.workspace_path,
                f"[sentinel] Plan created ({len(state.plan)} steps) | attempt {state.attempt_count}",
            )

        # ---------------------------------------------------------------------
        # 2. EXECUTING STAGE
        # ---------------------------------------------------------------------
        elif state.status == "executing":
            if state.current_step_index < len(state.plan):
                step_desc = state.plan[state.current_step_index]
                tool_res = execute_step(
                    state=state,
                    step_description=step_desc,
                    model_adapter=model_adapter,
                    fault_injector=fault_injector,
                )
                logger.log("tool_called", {
                    "step_index": state.current_step_index,
                    "description": step_desc,
                    "tool": tool_res.get("tool"),
                    "error": tool_res.get("error"),
                })
                state.current_step_index += 1
                ckpt_id = save_checkpoint(state, checkpoint_dir=checkpoint_dir)
                logger.log("checkpoint_saved", {"checkpoint_id": ckpt_id})
            else:
                # All plan steps executed; transition to verification
                state.status = "verifying"

        # ---------------------------------------------------------------------
        # 3. VERIFYING STAGE
        # ---------------------------------------------------------------------
        elif state.status == "verifying":
            v_res = verify_task(
                workspace_path=state.workspace_path,
                test_command=test_command,
                expected_files=expected_files,
            )
            state.verifier_result = v_res
            logger.log("verifier_evaluated", {
                "passed": v_res["passed"],
                "exit_code": v_res["test_exit_code"],
                "files_changed": v_res["files_changed"],
                "detail": v_res["detail"],
            })

            if v_res["passed"]:
                state.status = "done"
                logger.log("task_finished", {"status": "done", "attempts": state.attempt_count})
                save_checkpoint(state, checkpoint_dir=checkpoint_dir)
                break
            else:
                state.status = "recovering"

        # ---------------------------------------------------------------------
        # 4. RECOVERY STAGE
        # ---------------------------------------------------------------------
        elif state.status == "recovering":
            action, rationale = recovery_controller.evaluate(state)
            logger.log("recovery_triggered", {
                "action": action.value,
                "rationale": rationale,
                "attempt": state.attempt_count + 1,
            })

            if action == RecoveryAction.ABORT_FAIL:
                recovery_controller.apply_recovery(state, action, rationale)
                state.status = "failed"
                logger.log("task_finished", {"status": "failed", "reason": rationale})
                save_checkpoint(state, checkpoint_dir=checkpoint_dir)
                break

            current_attempts = state.attempt_count
            latest_verifier_result = state.verifier_result
            prior_tool_calls = list(state.tool_call_log)

            # Roll back workspace to last known good checkpoint to wipe corrupted diffs.
            # NOTE: git worktree is cleaned (checkout -- . + clean -fd) but
            # tool_call_log + verifier_result are preserved for audit, while
            # plan position resets to 0 and injected_fault is consumed.
            if last_good_checkpoint_id:
                state = rollback_to_checkpoint(
                    state,
                    last_good_checkpoint_id,
                    checkpoint_dir=checkpoint_dir,
                    revert_git_workspace=True,
                )
                state.attempt_count = current_attempts
                state.verifier_result = latest_verifier_result
                state.tool_call_log = prior_tool_calls
                state.injected_fault = None

            # Apply recovery action (replan, retry, or escalate)
            state = recovery_controller.apply_recovery(state, action, rationale)
            state.status = "executing"
            state.current_step_index = 0  # Re-enter plan execution from step 0
            save_checkpoint(state, checkpoint_dir=checkpoint_dir)

    if ticks >= max_loop_ticks and state.status not in ("done", "failed"):
        state.status = "failed"
        logger.log("task_finished", {"status": "failed", "reason": "Max loop ticks exceeded"})

    return state
