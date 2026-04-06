from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, input_text: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
