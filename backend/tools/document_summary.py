from __future__ import annotations

from typing import Any

from .base import BaseTool


class DocumentSummaryTool(BaseTool):
    name = "document_summary"
    description = "Summarize retrieved document context."

    def __init__(self, llm_callable: Any) -> None:
        self.llm_callable = llm_callable

    def run(self, input_text: str, context: dict[str, Any]) -> dict[str, Any]:
        retrieved = context.get("retrieved_contexts", [])
        joined = "\n\n".join(item.get("text", "") for item in retrieved[:8])

        prompt = f"""
Summarize the following document context for the user request.

User request:
{input_text}

Context:
{joined}
""".strip()

        summary = self.llm_callable(prompt)

        sources = sorted({item.get("source", "unknown") for item in retrieved})
        return {
            "summary": summary,
            "sources": sources,
        }
