from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BaseTool


class AuditLookupTool(BaseTool):
    name = "audit_lookup"
    description = "Look up audit activity from a local JSONL audit log."

    def __init__(self, audit_file: Path) -> None:
        self.audit_file = audit_file

    def run(self, input_text: str, context: dict[str, Any]) -> dict[str, Any]:
        query = input_text.lower().strip()
        matches: list[dict[str, Any]] = []

        if not self.audit_file.exists():
            return {
                "events": [],
                "count": 0,
                "warning": f"audit file not found: {self.audit_file}",
            }

        with self.audit_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                haystack = json.dumps(event).lower()
                if query in haystack:
                    matches.append(event)

        return {
            "events": matches[:25],
            "count": len(matches),
        }
