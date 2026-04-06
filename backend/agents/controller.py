from __future__ import annotations

import uuid
from datetime import UTC, datetime

from .executor import Executor
from .memory import FileMemoryStore
from .planner import Planner
from .schemas import AgentPlan, AgentResponse, AgentTrace, SessionMemory
from backend.evaluation.traces import JsonlTraceStore
from backend.tools.base import BaseTool


class AgentController:
    """
    Main orchestration layer for Agent V1.
    Coordinates planning, execution, response composition, memory, and tracing.
    """

    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        tool_registry: dict[str, BaseTool],
        memory_store: FileMemoryStore | None = None,
        trace_store: JsonlTraceStore | None = None,
    ) -> None:
        self.planner = planner
        self.executor = executor
        self.tool_registry = tool_registry
        self.memory_store = memory_store
        self.trace_store = trace_store

    def run(
        self,
        query: str,
        session_id: str | None = None,
        top_k: int = 5,
    ) -> AgentResponse:
        trace_id = str(uuid.uuid4())
        started = datetime.now(UTC)

        memory: SessionMemory | None = None
        if session_id and self.memory_store:
            memory = self.memory_store.load(session_id)

        plan: AgentPlan = self.planner.make_plan(query)

        base_context = {
            "top_k": top_k,
            "session_id": session_id,
        }
        if memory:
            base_context["memory"] = memory.model_dump()

        step_results = self.executor.run(plan, self.tool_registry, base_context)
        response = self._compose_response(query, session_id, plan, step_results)

        if session_id and self.memory_store:
            updated = memory or SessionMemory(session_id=session_id)
            updated.recent_queries.append(query)
            updated.recent_answers.append(response.answer)
            updated.referenced_sources.extend(response.evidence)

            updated.recent_queries = updated.recent_queries[-10:]
            updated.recent_answers = updated.recent_answers[-10:]
            updated.referenced_sources = list(dict.fromkeys(updated.referenced_sources))[-20:]

            self.memory_store.save(updated)

        if self.trace_store:
            total_latency_ms = max(
                0,
                int((datetime.now(UTC) - started).total_seconds() * 1000),
            )
            trace = AgentTrace(
                trace_id=trace_id,
                timestamp=started.isoformat(),
                session_id=session_id,
                user_query=query,
                plan=plan,
                step_results=step_results,
                final_response=response,
                total_latency_ms=total_latency_ms,
                success=all(step.success for step in step_results),
            )
            self.trace_store.append(trace)

        return response

    def _compose_response(
        self,
        query: str,
        session_id: str | None,
        plan: AgentPlan,
        step_results: list,
    ) -> AgentResponse:
        tools_used = [s.tool for s in step_results if s.success]
        evidence: list[str] = []

        for step in step_results:
            if not step.success:
                continue
            vals = step.output.get("sources", [])
            if isinstance(vals, list):
                evidence.extend(str(v) for v in vals)

        evidence = list(dict.fromkeys(evidence))

        final_text = "I don't know based on the provided documents."
        reasoning = plan.strategy
        confidence = 0.60
        structured_answer: dict[str, object] = {}

        last_success = next((s for s in reversed(step_results) if s.success), None)
        if last_success:
            output = last_success.output

            if "summary" in output:
                final_text = output["summary"]
                confidence = 0.82

            elif "analysis" in output:
                analysis = output["analysis"]

                if isinstance(analysis, dict):
                    structured_answer = analysis

                    requirements = analysis.get("requirements", []) or []
                    prohibited = analysis.get("prohibited_actions", []) or []
                    conditions = analysis.get("conditions", []) or []
                    conclusion = analysis.get("conclusion", "") or ""

                    lines: list[str] = []

                    if requirements:
                        lines.append("Requirements:")
                        lines.extend([f"- {x}" for x in requirements])

                    if prohibited:
                        lines.append("")
                        lines.append("Prohibited actions:")
                        lines.extend([f"- {x}" for x in prohibited])

                    if conditions:
                        lines.append("")
                        lines.append("Conditions:")
                        lines.extend([f"- {x}" for x in conditions])

                    if conclusion:
                        lines.append("")
                        lines.append(f"Conclusion: {conclusion}")

                    final_text = "\n".join(lines) if lines else "I don't know based on the provided documents."
                    
                    confidence = 0.86
                else:
                    final_text = str(analysis)
                    confidence = 0.80

            elif "contexts" in output:
                contexts = output["contexts"]
                if contexts:
                    final_text = "\n\n".join(
                        [
                            f"[Source: {c.get('source')}"
                            f"{' | page=' + str(c.get('page')) if c.get('page') is not None else ''}]"
                            f"\n{c.get('text', '')}"
                            for c in contexts[:3]
                        ]
                    )
                    confidence = 0.75

            elif "events" in output:
                count = output.get("count", 0)
                final_text = f"Found {count} matching audit events for: {query}"
                confidence = 0.80

        return AgentResponse(
            answer=final_text,
            reasoning_summary=reasoning,
            tools_used=tools_used,
            evidence=evidence,
            confidence=confidence,
            session_id=session_id,
            structured_answer=structured_answer,
            plan=plan,
            step_results=step_results,
        )