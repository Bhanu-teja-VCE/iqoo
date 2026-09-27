"""
Append-Only Trace Logger for Sentinel.
Emits structured JSONL events throughout task execution.
Powers live trace viewing and evaluation scorecard metrics.
"""

import json
import os
import tempfile
import time
from typing import Any


def get_default_traces_dir() -> str:
    """Return platform-appropriate base directory for execution traces."""
    if "SENTINEL_TRACES_DIR" in os.environ:
        return os.path.abspath(os.environ["SENTINEL_TRACES_DIR"])
    return os.path.abspath(os.path.join(tempfile.gettempdir(), "sentinel-traces"))


class TraceLogger:
    """
    Append-only structured JSONL event logger.
    Every event is saved with an accurate timestamp and task ID.
    """

    def __init__(self, task_id: str, traces_dir: str | None = None):
        self.task_id = task_id
        self.base_dir = traces_dir or get_default_traces_dir()
        os.makedirs(self.base_dir, exist_ok=True)
        self.trace_file = os.path.join(self.base_dir, f"{task_id}.jsonl")

    def log(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Record a structured event to the append-only JSONL log.
        Schema: {task_id, timestamp, event_type, data, payload}
        `data` is canonical; `payload` is a backwards-compatible alias
        (older architecture docs refer to `payload`).
        Returns the logged event dictionary.
        """
        body = payload or {}
        event = {
            "task_id": self.task_id,
            "timestamp": time.time(),
            "event_type": event_type,
            "data": body,
            "payload": body,
        }

        line = json.dumps(event) + "\n"
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(line)

        return event

    def read_events(self) -> list[dict[str, Any]]:
        """Read all events from this task's trace log."""
        if not os.path.isfile(self.trace_file):
            return []

        events = []
        with open(self.trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line_clean = line.strip()
                if line_clean:
                    events.append(json.loads(line_clean))
        return events


def read_task_trace(task_id: str, traces_dir: str | None = None) -> list[dict[str, Any]]:
    """Convenience helper to read all events for a given task ID."""
    logger = TraceLogger(task_id=task_id, traces_dir=traces_dir)
    return logger.read_events()
