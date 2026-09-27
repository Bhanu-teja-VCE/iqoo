"""
Executor Component for Sentinel.
Prompts model for tool actions per plan step and executes them strictly inside the sandbox.
Applies active chaos faults before sandbox boundary execution.
"""

import json
import re
import time
from typing import Any

from sentinel.agent.model_adapter import ModelAdapter
from sentinel.chaos.injector import FailureInjector
from sentinel.core.types import TaskState
from sentinel.sandbox.tools import (
    read_file,
    run_shell,
    run_tests,
    write_file,
)

EXECUTOR_SYSTEM_PROMPT = """You are an autonomous software engineering executor.
You have access ONLY to the following sandboxed tool API:
- read_file(path: str)
- write_file(path: str, content: str)
- run_shell(cmd: str)
- run_tests(test_command: str)

Propose ONE tool call to execute the given step as a JSON object:
{
  "tool": "write_file",
  "args": {
    "path": "math_module.py",
    "content": "def calculate_tax(price):\\n    return price * 0.10\\n"
  }
}
Do not include commentary. Output ONLY the JSON object.
"""


def execute_step(
    state: TaskState,
    step_description: str,
    model_adapter: ModelAdapter,
    fault_injector: FailureInjector | None = None,
) -> dict[str, Any]:
    """
    Execute a single plan step:
    1. Ask model to propose a tool call.
    2. Apply chaos injection if evaluation fault is active.
    3. Execute the tool within sandbox boundaries.
    4. Append the structured result to state.tool_call_log.
    """
    prompt = (
        f"Task Instruction: {state.instruction}\n"
        f"Current Step: {step_description}\n"
        f"Workspace Root: {state.workspace_path}\n"
        f"Prior Tool Calls Count: {len(state.tool_call_log)}\n"
        "Propose the next tool call as JSON."
    )

    raw_response = model_adapter.generate(prompt, system_prompt=EXECUTOR_SYSTEM_PROMPT)

    tool_call = _parse_tool_call(raw_response)
    tool_name = tool_call.get("tool", "run_shell")
    args = tool_call.get("args", {})

    # Apply chaos fault injection before running tool
    if fault_injector and state.injected_fault:
        fault_to_apply = state.injected_fault
        if tool_name == "write_file" and "content" in args:
            corrupted, _ = fault_injector.inject_write_fault(
                args["content"],
                fault_to_apply,
            )
            args["content"] = corrupted
            # Fault applied; clear so recovery attempt can cleanly repair state
            state.injected_fault = None
        elif tool_name in ("run_shell", "run_tests"):
            cmd_str = args.get("cmd") or args.get("test_command", "pytest")
            mod_tokens, mod_timeout, _ = fault_injector.inject_execution_fault(
                cmd_str.split(),
                args.get("timeout", 30),
                fault_to_apply,
            )
            injected_cmd = " ".join(mod_tokens)
            args["cmd"] = injected_cmd
            args["test_command"] = injected_cmd  # Ensure fault can't be bypassed via alternate key
            args["timeout"] = mod_timeout
            state.injected_fault = None

    # Execute tool within sandbox
    result: dict[str, Any]
    try:
        if tool_name == "read_file":
            result = read_file(args.get("path", ""), state.workspace_path)
        elif tool_name == "write_file":
            result = write_file(args.get("path", ""), args.get("content", ""), state.workspace_path)
        elif tool_name == "run_tests":
            result = run_tests(
                args.get("test_command") or args.get("cmd", "pytest"),
                state.workspace_path,
                timeout=args.get("timeout", 60),
            )
        else:  # Default run_shell
            result = run_shell(
                args.get("cmd", "ls"),
                state.workspace_path,
                timeout=args.get("timeout", 30),
            )
    except Exception as e:
        result = {
            "tool": tool_name,
            "args": args,
            "result": {},
            "error": f"Execution exception: {e}",
        }

    # Record to state tool call log
    state.tool_call_log.append({
        "timestamp": time.time(),
        "step_index": state.current_step_index,
        "step_description": step_description,
        "tool_call": result,
    })

    return result


def _parse_tool_call(raw_text: str) -> dict[str, Any]:
    """Extract tool and args dictionary from raw model text."""
    # 1. Direct JSON parse
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict) and "tool" in parsed:
            return parsed
    except Exception:
        pass

    # 2. Extract JSON block
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "tool" in parsed:
                return parsed
        except Exception:
            pass

    # 3. Default fallback tool call
    return {
        "tool": "run_shell",
        "args": {"cmd": "ls"},
    }
