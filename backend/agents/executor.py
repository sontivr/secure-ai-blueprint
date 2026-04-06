from __future__ import annotations

import time
from typing import Any

from .schemas import AgentPlan, StepResult
from backend.tools.base import BaseTool


class Executor:
    """
    Executes AgentPlan steps in order, resolving dependencies and
    passing prior outputs into downstream tools.
    """

    def run(
        self,
        plan: AgentPlan,
        tool_registry: dict[str, BaseTool],
        base_context: dict[str, Any],
    ) -> list[StepResult]:
        results: list[StepResult] = []
        result_index: dict[str, StepResult] = {}

        for step in plan.steps:
            started = time.perf_counter()

            if step.tool not in tool_registry:
                result = StepResult(
                    step_id=step.step_id,
                    tool=step.tool,
                    success=False,
                    error=f"tool not registered: {step.tool}",
                    latency_ms=0,
                )
                results.append(result)
                result_index[step.step_id] = result
                continue

            context = dict(base_context)

            dependency_outputs: list[dict[str, Any]] = []
            failed_dependencies: list[str] = []

            for dep_id in step.depends_on:
                dep_result = result_index.get(dep_id)
                if not dep_result or not dep_result.success:
                    failed_dependencies.append(dep_id)
                else:
                    dependency_outputs.append(dep_result.output)

            if failed_dependencies:
                result = StepResult(
                    step_id=step.step_id,
                    tool=step.tool,
                    success=False,
                    error=f"dependency failure: {', '.join(failed_dependencies)}",
                    latency_ms=0,
                )
                results.append(result)
                result_index[step.step_id] = result
                continue

            if dependency_outputs:
                context["dependency_outputs"] = dependency_outputs

                retrieved_contexts: list[dict[str, Any]] = []
                for dep in dependency_outputs:
                    retrieved_contexts.extend(dep.get("contexts", []))
                context["retrieved_contexts"] = retrieved_contexts
                
            tool = tool_registry[step.tool]

            try:
                output = tool.run(step.input_text, context)
                latency_ms = int((time.perf_counter() - started) * 1000)
                result = StepResult(
                    step_id=step.step_id,
                    tool=step.tool,
                    success=True,
                    output=output,
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                result = StepResult(
                    step_id=step.step_id,
                    tool=step.tool,
                    success=False,
                    error=str(exc),
                    latency_ms=latency_ms,
                )

            results.append(result)
            result_index[step.step_id] = result

        return results
