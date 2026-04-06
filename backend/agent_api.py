from __future__ import annotations

from fastapi import APIRouter, Depends

from .agents.controller import AgentController
from .agents.executor import Executor
from .agents.memory import FileMemoryStore
from .agents.planner import Planner
from .agents.schemas import AgentQueryRequest, AgentResponse
from .config import DATA_DIR, AUDIT_LOG_PATH
from .evaluation.traces import JsonlTraceStore
from .rag_pipeline import RagStore, ollama_chat
from .rbac import get_current_user
from .tools.audit_lookup import AuditLookupTool
from .tools.document_summary import DocumentSummaryTool
from .tools.policy_check import PolicyCheckTool
from .tools.rag_search import RagSearchTool

router = APIRouter(prefix="/agent", tags=["agent"])

store = RagStore()


def build_tool_registry():
    return {
        "rag_search": RagSearchTool(rag_store=store),
        "document_summary": DocumentSummaryTool(llm_callable=ollama_chat),
        "policy_check": PolicyCheckTool(llm_callable=ollama_chat),
        "audit_lookup": AuditLookupTool(audit_file=AUDIT_LOG_PATH),
    }


controller = AgentController(
    planner=Planner(),
    executor=Executor(),
    tool_registry=build_tool_registry(),
    memory_store=FileMemoryStore(DATA_DIR / "agent-memory"),
    trace_store=JsonlTraceStore(DATA_DIR / "agent_traces.jsonl"),
)


@router.post("/query", response_model=AgentResponse)
def agent_query(
    request: AgentQueryRequest,
    user=Depends(get_current_user),
) -> AgentResponse:
    session_id = request.session_id or user["username"]

    return controller.run(
        query=request.query,
        session_id=session_id,
        top_k=request.top_k,
    )


@router.get("/health")
def agent_health(user=Depends(get_current_user)) -> dict:
    return {
        "status": "ok",
        "tools": list(build_tool_registry().keys()),
        "memory_dir": str(DATA_DIR / "agent-memory"),
        "trace_file": str(DATA_DIR / "agent_traces.jsonl"),
    }