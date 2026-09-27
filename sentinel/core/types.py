"""
TaskState Schema for Sentinel.
The single serializable state container that every component reads and writes.
Nothing lives only inside an LLM's context window.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TaskState:
    """
    Unified state representation for a Sentinel task.
    Enables deterministic checkpointing, resume-after-kill, and state rollback.
    """
    task_id: str
    workspace_path: str
    instruction: str
    plan: list[str] = field(default_factory=list)
    current_step_index: int = 0
    tool_call_log: list[dict[str, Any]] = field(default_factory=list)
    attempt_count: int = 0
    injected_fault: str | None = None
    verifier_result: dict[str, Any] | None = None
    status: str = "planning"  # planning | executing | verifying | recovering | done | failed
    model_used: str = "local"  # "local" | "frontier"
    checkpoint_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert state to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        """Reconstruct TaskState from a dictionary."""
        return cls(
            task_id=data["task_id"],
            workspace_path=data["workspace_path"],
            instruction=data["instruction"],
            plan=data.get("plan", []),
            current_step_index=data.get("current_step_index", 0),
            tool_call_log=data.get("tool_call_log", []),
            attempt_count=data.get("attempt_count", 0),
            injected_fault=data.get("injected_fault"),
            verifier_result=data.get("verifier_result"),
            status=data.get("status", "planning"),
            model_used=data.get("model_used", "local"),
            checkpoint_id=data.get("checkpoint_id"),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize state to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "TaskState":
        """Deserialize state from JSON string."""
        return cls.from_dict(json.loads(json_str))
