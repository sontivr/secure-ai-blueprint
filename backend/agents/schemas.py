from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ToolName = Literal[
    "rag_search",
    "document_summary",
    "policy_check",
    "audit_lookup",
]


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["agent", "direct"] = "agent"


class PlanStep(BaseModel):
    step_id: str
    tool: ToolName
    purpose: str
    input_text: str
    depends_on: list[str] = Field(default_factory=list)


class AgentPlan(BaseModel):
    goal: str
    strategy: str
    steps: list[PlanStep]
    final_response_style: Literal["concise", "detailed", "structured"] = "structured"


class StepResult(BaseModel):
    step_id: str
    tool: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    latency_ms: int | None = None


class AgentResponse(BaseModel):
    answer: str
    reasoning_summary: str
    tools_used: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    session_id: str | None = None
    structured_answer: dict[str, Any] = Field(default_factory=dict)
    plan: AgentPlan | None = None
    step_results: list[StepResult] = Field(default_factory=list)

class SessionMemory(BaseModel):
    session_id: str
    recent_queries: list[str] = Field(default_factory=list)
    recent_answers: list[str] = Field(default_factory=list)
    referenced_sources: list[str] = Field(default_factory=list)


class AgentTrace(BaseModel):
    trace_id: str
    timestamp: str
    session_id: str | None = None
    user_query: str
    plan: AgentPlan
    step_results: list[StepResult]
    final_response: AgentResponse
    total_latency_ms: int
    success: bool
