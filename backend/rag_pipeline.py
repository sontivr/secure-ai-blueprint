from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import requests

from .config import CHROMA_DIR, EMBED_MODEL, OLLAMA_BASE_URL, OLLAMA_MODEL, ANONYMIZED_TELEMETRY

from .logger import get_logger

logger = get_logger(__name__)

@dataclass
class Chunk:
    text: str
    source: str
    chunk_id: str
    metadata: dict

def _chunk_text(
    text: str,
    source: str,
    base_metadata: dict | None = None,
    max_chars: int = 1200,
    overlap: int = 150
) -> List[Chunk]:
    text = text.strip()
    if not text:
        return []

    base_metadata = base_metadata or {}
    chunks: List[Chunk] = []
    start = 0
    n = len(text)
    chunk_index = 0

    while start < n:
        end = min(start + max_chars, n)
        chunk_txt = text[start:end].strip()

        if chunk_txt:
            h = hashlib.sha256((source + "::" + chunk_txt).encode("utf-8")).hexdigest()[:16]
            metadata = dict(base_metadata)
            metadata["source"] = source
            metadata["chunk_index"] = chunk_index

            chunks.append(
                Chunk(
                    text=chunk_txt,
                    source=source,
                    chunk_id=f"{source}:{h}",
                    metadata=metadata
                )
            )
            chunk_index += 1

        if end >= n:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks

class RagStore:
    def __init__(self, collection_name: str = "documents"):
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=ANONYMIZED_TELEMETRY),
        )
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.embedder = SentenceTransformer(EMBED_MODEL)

    def upsert_text(self, text: str, source: str) -> Dict[str, Any]:
        logger.info(f"upsert_text start source={source}")
        chunks = _chunk_text(text, source=source)
        logger.info(f"chunk count={len(chunks)}")
    
        if not chunks:
            logger.info("no chunks")
            return {"upserted": 0}
    
        ids = [c.chunk_id for c in chunks]
        docs = [c.text for c in chunks]
        metas = [c.metadata for c in chunks]
    
        logger.info("encoding embeddings...")
        embs = self.embedder.encode(docs, normalize_embeddings=True).tolist()
        logger.info("embeddings encoded")
    
        logger.info("writing to chroma...")
        self.collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
        logger.info("upsert complete")
    
        return {"upserted": len(ids)}

    def query(self, q: str, k: int = 5) -> List[Dict[str, Any]]:
        logger.info(f"query start k={k}")
        q_emb = self.embedder.encode([q], normalize_embeddings=True).tolist()
        logger.info("query embedding done")
    
        res = self.collection.query(
            query_embeddings=q_emb,
            n_results=k,
            include=["documents", "metadatas", "distances"]
        )
        logger.info(f"raw query result keys={list(res.keys())}")
    
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        ids = res.get("ids", [[]])[0] if "ids" in res else [None] * len(docs)
    
        out = []
        for doc, meta, dist, _id in zip(docs, metas, dists, ids):
            meta = meta or {}
            out.append({
                "id": _id,
                "source": meta.get("source"),
                "page": meta.get("page"),
                "chunk_index": meta.get("chunk_index"),
                "distance": dist,
                "text": doc
            })    

        logger.info(f"query returning {len(out)} contexts")
        return out
    
    def upsert_pages(self, pages: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        all_chunks: List[Chunk] = []

        for page in pages:
            page_num = page["page"]
            text = page["text"]

            chunks = _chunk_text(
                text,
                source=source,
                base_metadata={"page": page_num}
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            return {"upserted": 0}

        ids = [c.chunk_id for c in all_chunks]
        docs = [c.text for c in all_chunks]
        metas = [c.metadata for c in all_chunks]
        embs = self.embedder.encode(docs, normalize_embeddings=True).tolist()

        self.collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
        return {"upserted": len(ids)}

def ollama_chat(prompt: str, system: Optional[str] = None) -> str:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt if system is None else f"{system}\n\n{prompt}",
        "stream": False,
    }

    logger.info(f"POST {url} model={OLLAMA_MODEL}")
    r = requests.post(url, json=payload, timeout=120)
    logger.info(f"status={r.status_code}")
    r.raise_for_status()

    data = r.json()
    logger.info(f"response keys={list(data.keys())}")
    return data.get("response", "").strip()

def build_prompt(question: str, contexts: List[Dict[str, Any]]) -> str:
    if not contexts:
        context_block = "[NO CONTEXT RETRIEVED]"
    else:
        context_block = "\n\n".join([
            (
                f"[Source: {c.get('source') or 'unknown'}"
                f"{' | page=' + str(c.get('page')) if c.get('page') is not None else ''}"
                f" | id={c.get('id')}]\n{c.get('text')}"
            )
            for c in contexts
        ])

    return f"""You are a grounded AI assistant for regulated document workflows.

Rules:
1. Use ONLY the provided context.
2. Do NOT use outside knowledge.
3. If the context does not directly answer the question, say exactly: "I don't know based on the provided documents."
4. Do not infer missing facts from partial matches.
5. Be concise and factual.
6. Cite supporting evidence using source and page when available.

Return your answer in this format:

Answer:
<short answer>

Evidence:
- <source/page/id reference 1>
- <source/page/id reference 2 if applicable>

CONTEXT:
{context_block}

QUESTION:
{question}
"""
