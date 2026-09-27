"""
Planner Component for Sentinel.
Generates an ordered list of atomic execution steps for a given task instruction.
"""

import json
import re
from typing import Any

from sentinel.agent.model_adapter import ModelAdapter
from sentinel.core.types import TaskState

PLANNER_SYSTEM_PROMPT = """You are a precise software engineering planning agent.
Your objective is to analyze a bug or feature request and break it down into an ordered sequence of 2 to 4 atomic steps.
Your output MUST be a valid JSON array of strings, for example:
[
  "Read the target module to understand current implementation",
  "Write corrected logic to target module to fix bug",
  "Run test suite to verify fix"
]
Do not output conversational commentary. Output ONLY the JSON array.
"""


def generate_plan(state: TaskState, model_adapter: ModelAdapter) -> list[str]:
    """
    Produce an ordered list of execution steps for the given TaskState.
    Returns the generated list of step strings.
    """
    prompt = (
        f"Task Instruction: {state.instruction}\n"
        f"Workspace Path: {state.workspace_path}\n"
        f"Injected Fault Mode: {state.injected_fault or 'None'}\n\n"
        "Generate the ordered plan as a JSON list of step descriptions."
    )

    raw_response = model_adapter.generate(prompt, system_prompt=PLANNER_SYSTEM_PROMPT)

    # 1. Direct JSON parse
    try:
        parsed = json.loads(raw_response)
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            state.plan = parsed
            return parsed
    except Exception:
        pass

    # 2. Extract JSON array inside markdown code blocks
    json_match = re.search(r"\[.*\]", raw_response, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, list):
                state.plan = [str(item) for item in parsed]
                return state.plan
        except Exception:
            pass

    # 3. Fallback: Parse numbered list lines (e.g. "1. Read file\n2. Write fix")
    lines = [
        re.sub(r"^\d+[\.\)]\s*", "", line.strip())
        for line in raw_response.splitlines()
        if line.strip() and not line.strip().startswith(("{", "}", "[", "]", "```"))
    ]
    if lines:
        state.plan = lines
        return lines

    # 4. Default deterministic plan
    default_plan = [
        f"Investigate: {state.instruction}",
        f"Implement fix for: {state.instruction}",
        "Run verification test suite",
    ]
    state.plan = default_plan
    return default_plan
