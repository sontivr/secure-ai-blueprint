from __future__ import annotations

from .schemas import AgentPlan, PlanStep


class Planner:
    """
    Rule-based planner for Agent V1.

    This is intentionally simple so the agent layer is stable and testable.
    Later, this can be replaced or augmented with an LLM-driven planner.
    """

    def make_plan(self, query: str) -> AgentPlan:
        q = query.lower().strip()

        if any(word in q for word in ["audit", "event", "log", "history"]):
            return AgentPlan(
                goal="Find audit information related to the user query.",
                strategy="Use audit lookup directly.",
                steps=[
                    PlanStep(
                        step_id="s1",
                        tool="audit_lookup",
                        purpose="Search audit records",
                        input_text=query,
                    )
                ],
                final_response_style="structured",
            )

        if any(word in q for word in ["summary", "summarize", "overview"]):
            return AgentPlan(
                goal="Summarize relevant content for the user query.",
                strategy="Retrieve relevant context, then summarize it.",
                steps=[
                    PlanStep(
                        step_id="s1",
                        tool="rag_search",
                        purpose="Find relevant context",
                        input_text=query,
                    ),
                    PlanStep(
                        step_id="s2",
                        tool="document_summary",
                        purpose="Summarize retrieved context",
                        input_text=query,
                        depends_on=["s1"],
                    ),
                ],
                final_response_style="concise",
            )

        if any(
            word in q
            for word in [
                "must",
                "required",
                "requirement",
                "policy",
                "allowed",
                "prohibited",
                "remote access",
                "mfa",
            ]
        ):
            return AgentPlan(
                goal="Answer a policy-oriented question with evidence.",
                strategy="Retrieve context, then extract structured policy findings.",
                steps=[
                    PlanStep(
                        step_id="s1",
                        tool="rag_search",
                        purpose="Find policy-relevant context",
                        input_text=query,
                    ),
                    PlanStep(
                        step_id="s2",
                        tool="policy_check",
                        purpose="Extract requirements and policy findings",
                        input_text=query,
                        depends_on=["s1"],
                    ),
                ],
                final_response_style="structured",
            )

        return AgentPlan(
            goal="Answer the user's question using document retrieval.",
            strategy="Use retrieval and provide document-grounded context.",
            steps=[
                PlanStep(
                    step_id="s1",
                    tool="rag_search",
                    purpose="Find relevant evidence",
                    input_text=query,
                )
            ],
            final_response_style="detailed",
        )
