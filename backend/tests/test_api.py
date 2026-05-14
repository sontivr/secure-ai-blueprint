"""
Integration tests for all FastAPI endpoints.

Uses the `client`, `admin_token`, and `user_token` fixtures from conftest.py.
External dependencies (ChromaDB, Ollama, sentence-transformers) are replaced by
MagicMock via `mock_store` and patched callables — no real I/O occurs.
"""
from __future__ import annotations

from unittest.mock import patch


# ---------------------------------------------------------------------------
# /health  (liveness)
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_body_contains_status_ok(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_unaffected_by_dep_failures(self, client, mock_store):
        # Liveness must stay up even when dependencies are broken
        mock_store.client.heartbeat.side_effect = RuntimeError("chromadb unreachable")
        assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# /ready  (readiness — probes ChromaDB + Ollama)
# ---------------------------------------------------------------------------

class TestReady:
    def test_200_when_all_deps_healthy(self, client, mock_store):
        mock_store.client.heartbeat.return_value = None
        with patch("backend.main.requests.get") as mock_get:
            mock_get.return_value.ok = True
            resp = client.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["chromadb"] == "ok"
        assert body["ollama"] == "ok"

    def test_503_when_chromadb_down(self, client, mock_store):
        mock_store.client.heartbeat.side_effect = RuntimeError("chroma down")
        with patch("backend.main.requests.get") as mock_get:
            mock_get.return_value.ok = True
            resp = client.get("/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"
        assert "error" in resp.json()["chromadb"]

    def test_503_when_ollama_unreachable(self, client, mock_store):
        mock_store.client.heartbeat.return_value = None
        with patch("backend.main.requests.get", side_effect=ConnectionError("refused")):
            resp = client.get("/ready")
        assert resp.status_code == 503
        assert "error" in resp.json()["ollama"]

    def test_503_when_ollama_returns_error_status(self, client, mock_store):
        mock_store.client.heartbeat.return_value = None
        with patch("backend.main.requests.get") as mock_get:
            mock_get.return_value.ok = False
            mock_get.return_value.status_code = 503
            resp = client.get("/ready")
        assert resp.status_code == 503
        assert resp.json()["ollama"] == "http_503"


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_admin_login_returns_token_and_role(self, client):
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["role"] == "admin"

    def test_user_login_returns_user_role(self, client):
        resp = client.post("/auth/login", json={"username": "user", "password": "user123"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"

    def test_wrong_password_returns_401(self, client):
        resp = client.post("/auth/login", json={"username": "admin", "password": "badpass"})
        assert resp.status_code == 401

    def test_unknown_user_returns_401(self, client):
        resp = client.post("/auth/login", json={"username": "ghost", "password": "any"})
        assert resp.status_code == 401

    def test_rate_limit_after_10_requests(self, client):
        payload = {"username": "admin", "password": "wrongpassword"}
        # First 10 attempts: rejected for bad credentials but not rate-limited
        for _ in range(10):
            r = client.post("/auth/login", json=payload)
            assert r.status_code == 401

        # 11th attempt: rate-limited
        r = client.post("/auth/login", json=payload)
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# /ingest/text
# ---------------------------------------------------------------------------

class TestIngestText:
    def test_admin_can_ingest(self, client, admin_token, mock_store):
        resp = client.post(
            "/ingest/text",
            json={"source": "test.txt", "text": "Some document content here."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_user_role_is_forbidden(self, client, user_token):
        resp = client.post(
            "/ingest/text",
            json={"source": "test.txt", "text": "content"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_is_rejected(self, client):
        resp = client.post("/ingest/text", json={"source": "s", "text": "t"})
        assert resp.status_code == 403  # HTTPBearer raises 403 on missing creds


# ---------------------------------------------------------------------------
# /ingest/file
# ---------------------------------------------------------------------------

class TestIngestFile:
    def test_admin_can_upload_txt(self, client, admin_token, mock_store):
        resp = client.post(
            "/ingest/file?source=upload.txt",
            files={"file": ("upload.txt", b"Hello from file.", "text/plain")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_non_txt_returns_400(self, client, admin_token):
        resp = client.post(
            "/ingest/file?source=doc",
            files={"file": ("doc.pdf", b"%PDF content", "application/pdf")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_user_role_is_forbidden(self, client, user_token):
        resp = client.post(
            "/ingest/file?source=f",
            files={"file": ("f.txt", b"content", "text/plain")},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /query
# ---------------------------------------------------------------------------

class TestQuery:
    def test_authenticated_user_can_query(self, client, user_token, mock_store):
        resp = client.post(
            "/query",
            json={"question": "What is the annual review policy?", "top_k": 3},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "contexts" in body

    def test_admin_can_query(self, client, admin_token):
        resp = client.post(
            "/query",
            json={"question": "What does the policy say?", "top_k": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_unauthenticated_is_rejected(self, client):
        resp = client.post("/query", json={"question": "test", "top_k": 3})
        assert resp.status_code == 403

    def test_no_context_returns_fallback_answer(self, client, user_token, mock_store):
        # Simulate no relevant chunks found (all distances too high)
        mock_store.query.return_value = [
            {"id": "c1", "source": "s.txt", "page": None, "chunk_index": 0,
             "distance": 9.99, "text": "Irrelevant."}
        ]
        resp = client.post(
            "/query",
            json={"question": "What is the meaning of life?", "top_k": 3},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "I don't know" in body["answer"]
        assert body["contexts"] == []

    def test_answer_format_contains_evidence_section(self, client, user_token):
        resp = client.post(
            "/query",
            json={"question": "What is the policy?", "top_k": 3},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        answer = resp.json()["answer"]
        assert "Answer:" in answer
        assert "Evidence:" in answer


# ---------------------------------------------------------------------------
# /audit/summary
# ---------------------------------------------------------------------------

class TestAuditSummary:
    def test_admin_gets_summary(self, client, admin_token):
        resp = client.get(
            "/audit/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert "counts" in resp.json()

    def test_user_is_forbidden(self, client, user_token):
        resp = client.get(
            "/audit/summary",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_is_rejected(self, client):
        resp = client.get("/audit/summary")
        assert resp.status_code == 403
