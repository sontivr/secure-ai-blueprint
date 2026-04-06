from __future__ import annotations

import json
from pathlib import Path

from backend.agents.schemas import AgentTrace


class JsonlTraceStore:
    """
    Appends agent execution traces to a JSONL file.
    """

    def __init__(self, trace_file: Path) -> None:
        self.trace_file = trace_file
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        self.trace_file.touch(exist_ok=True)

    def append(self, trace: AgentTrace) -> None:
        with self.trace_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trace.model_dump(), ensure_ascii=False) + "\n")
