from __future__ import annotations

import json
from pathlib import Path

from .schemas import SessionMemory


class FileMemoryStore:
    """
    Minimal file-backed session memory for Agent V1.
    Stores one JSON file per session_id.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def load(self, session_id: str) -> SessionMemory:
        path = self._path(session_id)
        if not path.exists():
            return SessionMemory(session_id=session_id)

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return SessionMemory.model_validate(data)

    def save(self, memory: SessionMemory) -> None:
        path = self._path(memory.session_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(memory.model_dump(), f, indent=2)
