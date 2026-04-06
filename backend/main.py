from __future__ import annotations

import time
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from .config import APP_NAME, ENV, MAX_RETRIEVAL_DISTANCE
from .auth import authenticate_user, create_access_token
from .rbac import get_current_user, require_role
from .audit_logger import write_audit, safe_truncate
from .rag_pipeline import RagStore, build_prompt, ollama_chat

from .pdf_utils import extract_pages_from_pdf
import tempfile

from .pii_redactor import redact_pii

from .logger import get_logger

from .agent_api import router as agent_router

logger = get_logger(__name__)


app = FastAPI(title=APP_NAME)
app.include_router(agent_router)

store = RagStore()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class IngestTextRequest(BaseModel):
    source: str = Field(..., description="Logical source label (e.g. policy-001.txt)")
    text: str

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    contexts: List[Dict[str, Any]]

@app.get("/health")
def health():
    return {"status": "ok", "env": ENV}

@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    logger.info("Login attempt: username=%s", req.username)
    u = authenticate_user(req.username, req.password)
    if not u:
        logger.warning("Login failed: username=%s", req.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=u["username"], role=u["role"])
    logger.info("Login successful: username=%s role=%s", u["username"], u["role"])

    return LoginResponse(access_token=token, role=u["role"])

@app.post("/ingest/text")
def ingest_text(req: IngestTextRequest, user=Depends(require_role("admin"))):
    logger.info("Text ingest requested: source=%s actor=%s", req.source, user["username"])

    t0 = time.time()
    result = store.upsert_text(req.text, source=req.source)
    ms = int((time.time() - t0) * 1000)

    write_audit({
        "event": "ingest_text",
        "actor": user["username"],
        "role": user["role"],
        "source": req.source,
        "upserted": result.get("upserted"),
        "latency_ms": ms,
    })

    logger.info(
        "event=ingest_text_completed source=%s chunks=%s latency_ms=%s",
        req.source,
        result.get("upserted"),
        ms
    )

    return {"ok": True, **result, "latency_ms": ms}

@app.post("/ingest/file")
async def ingest_file(source: str, file: UploadFile = File(...), user=Depends(require_role("admin"))):
    logger.info(
        "event=ingest_file_requested filename=%s actor=%s",
        file.filename,
        user["username"]
    )

    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Lean V1 supports .txt only")

    content = (await file.read()).decode("utf-8", errors="replace")
    t0 = time.time()
    result = store.upsert_text(content, source=source or file.filename)
    ms = int((time.time() - t0) * 1000)

    write_audit({
        "event": "ingest_file",
        "actor": user["username"],
        "role": user["role"],
        "filename": file.filename,
        "source": source or file.filename,
        "size_bytes": len(content.encode("utf-8")),
        "upserted": result.get("upserted"),
        "latency_ms": ms,
    })

    logger.info(
        "event=ingest_file_completed actor=%s filename=%s size_bytes=%s chunks=%s latency_ms=%s",
        user["username"],
        file.filename,
        len(content.encode("utf-8")),
        result.get("upserted"),
        ms
    )

    return {"ok": True, **result, "latency_ms": ms}

@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, user=Depends(get_current_user)):
    logger.info(
        "event=query_requested actor=%s top_k=%s",
        user["username"],
        req.top_k
    )

    t0 = time.time()
    try:
        logger.info("request received")
        logger.info(f"actor={user['username']} top_k={req.top_k}")

        logger.info("retrieving contexts...")
        contexts = store.query(req.question, k=req.top_k)
        MAX_DISTANCE = 1.2
        filtered_contexts = [c for c in contexts if c.get("distance") is not None and c["distance"] <= MAX_RETRIEVAL_DISTANCE]
        if not filtered_contexts:
            answer = (
                "Answer:\n"
                "I don't know based on the provided documents.\n\n"
                "Evidence:\n"
                "- No sufficiently relevant supporting passages were retrieved."
            )
            
            ms = int((time.time() - t0) * 1000)

            write_audit({
                "event": "query",
                "actor": user["username"],
                "role": user["role"],
                "question": safe_truncate(redact_pii(req.question), 300),
                "top_k": req.top_k,
                "context_ids": [],
                "latency_ms": ms,
                "answer_len": len(answer),
            })

            logger.info(
                "event=query_completed actor=%s top_k=%s contexts=%s latency_ms=%s",
                user["username"],
                req.top_k,
                0,
                ms
            )

            return QueryResponse(answer=answer, contexts=[])
        
        logger.info(f"filtered contexts retrieved: {len(filtered_contexts)}")

        logger.info("building prompt...")
        prompt = build_prompt(req.question, filtered_contexts)

        system = (
            "You are a document-grounded assistant. "
            "Answer only from the supplied context. "
            "Do not guess or use outside knowledge. "
            "If evidence is insufficient, say you do not know based on the provided documents."
        )

        logger.info("calling ollama...")
        answer = ollama_chat(prompt, system=system)
        if "Answer:" not in answer:
            answer = f"Answer:\n{answer}\n\nEvidence:\n- format not fully structured"
        logger.info("ollama returned")

        ms = int((time.time() - t0) * 1000)

        write_audit({
            "event": "query",
            "actor": user["username"],
            "role": user["role"],
            "question": safe_truncate(redact_pii(req.question), 300),
            "top_k": req.top_k,
            "context_ids": [c.get("id") for c in filtered_contexts],
            "latency_ms": ms,
            "answer_len": len(answer),
        })

        logger.info(
            "event=query_completed actor=%s top_k=%s contexts=%s latency_ms=%s",
            user["username"],
            req.top_k,
            len(contexts),
            ms
        )

        return QueryResponse(answer=answer, contexts=filtered_contexts)

    except Exception as e:
        import traceback
        traceback.print_exc()

        write_audit({
            "event": "query_error",
            "actor": user["username"],
            "role": user["role"],
            "question": safe_truncate(redact_pii(req.question), 300),
            "error": str(e),
        })

        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/audit/summary")
def audit_summary(user=Depends(require_role("admin"))):
    """
    Lean admin endpoint: returns count of events by type (reads from local JSONL).
    """

    logger.info(
        "event=audit_summary_requested actor=%s",
        user["username"]
    )

    from .config import AUDIT_LOG_PATH
    counts = {}
    if not AUDIT_LOG_PATH.exists():
        return {"counts": counts, "path": str(AUDIT_LOG_PATH)}

    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                import json
                ev = json.loads(line)
                k = ev.get("event", "unknown")
                counts[k] = counts.get(k, 0) + 1
            except Exception:
                counts["malformed"] = counts.get("malformed", 0) + 1

    logger.info(
        "event=audit_summary actor=%s event_types=%s",
        user["username"],
        list(counts.keys())
    )

    return {"counts": counts, "path": str(AUDIT_LOG_PATH)}

@app.post("/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...), user=Depends(require_role("admin"))):
    logger.info(
        "event=ingest_pdf_requested filename=%s actor=%s",
        file.filename,
        user["username"]
    )   

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    logger.info(f"event=ingest_pdf_received filename=%s", file.filename)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    pages = extract_pages_from_pdf(tmp_path)

    if not pages:
        raise HTTPException(status_code=400, detail="No text extracted from PDF")

    result = store.upsert_pages(pages, source=file.filename)

    write_audit({
        "event": "ingest_pdf",
        "actor": user["username"],
        "filename": file.filename,
        "chunks": result["upserted"]
    })

    logger.info(
        "event=ingest_pdf_completed filename=%s chunks=%s",
        file.filename,
        result["upserted"]
    )

    return {
        "message": "PDF ingested",
        "chunks": result["upserted"]
    }
