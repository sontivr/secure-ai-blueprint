# Secure AI Blueprint — Lean V1 Architecture
        +-----------------------+
        |     Streamlit UI      |
        | login / ingest / ask  |
        +-----------+-----------+
                    |
                    v
        +-----------------------+
        |      FastAPI API      |
        | Auth / RBAC / Query   |
        +-----------+-----------+
                    |
                    v
        +-----------------------+
        |    RAG Pipeline       |
        | chunk / embed / query |
        +-----------+-----------+
                    |
    +---------------+---------------+
    |                               |
    v                               v
    +—————+               +––––––––+
|  Chroma DB    |               |  Ollama LLM    |
| vector store  |               | local model    |
+—————+               +––––––––+
