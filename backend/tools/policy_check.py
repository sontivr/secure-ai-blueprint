from __future__ import annotations

import json
import re
from typing import Any

from .base import BaseTool


class PolicyCheckTool(BaseTool):
    name = "policy_check"
    description = "Extract policy requirements, prohibitions, and conditions from retrieved context."

    def __init__(self, llm_callable: Any) -> None:
        self.llm_callable = llm_callable

    def _extract_json_block(self, text: str) -> dict[str, Any]:
        text = text.strip()

        fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if fenced:
            candidate = fenced.group(1)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        plain = re.search(r"(\{.*\})", text, flags=re.DOTALL)
        if plain:
            candidate = plain.group(1)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        return {
            "requirements": [],
            "prohibited_actions": [],
            "conditions": [],
            "conclusion": text,
        }

    def run(self, input_text: str, context: dict[str, Any]) -> dict[str, Any]:
        retrieved = context.get("retrieved_contexts", [])
        joined = "\n\n".join(item.get("text", "") for item in retrieved[:8])

        prompt = f"""
You are a policy analysis assistant.

User question:
{input_text}

Using ONLY the context below, return valid JSON with exactly these keys:
requirements
prohibited_actions
conditions
conclusion

Rules:
- requirements must be a JSON array of strings
- prohibited_actions must be a JSON array of strings
- conditions must be a JSON array of strings
- conclusion must be a string
- do not include markdown
- do not include code fences
- if the context is insufficient, return empty arrays and set conclusion to:
  "I don't know based on the provided documents."

Context:
{joined}
""".strip()

        raw = self.llm_callable(prompt)
        parsed = self._extract_json_block(raw)

        sources = sorted(
            {
                f"{item.get('source')}{' page ' + str(item.get('page')) if item.get('page') is not None else ''}"
                for item in retrieved
            }
        )

        return {
            "analysis": parsed,
            "sources": sources,
        }