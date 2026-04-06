from __future__ import annotations

from typing import Any

from .base import BaseTool
from backend.rag_pipeline import RagStore
from backend.config import MAX_RETRIEVAL_DISTANCE


class RagSearchTool(BaseTool):
    name = "rag_search"
    description = "Retrieve relevant document chunks and evidence for a user query."

    def __init__(self, rag_store: RagStore) -> None:
        self.rag_store = rag_store

    def run(self, input_text: str, context: dict[str, Any]) -> dict[str, Any]:
        top_k = int(context.get("top_k", 5))
        contexts = self.rag_store.query(input_text, k=top_k)

        filtered = [
            c for c in contexts
            if c.get("distance") is not None and c["distance"] <= MAX_RETRIEVAL_DISTANCE
        ]

        sources = sorted(
            {
                f"{c.get('source')}{' page ' + str(c.get('page')) if c.get('page') is not None else ''}"
                for c in filtered
            }
        )

        return {
            "contexts": filtered,
            "sources": sources,
            "count": len(filtered),
        }