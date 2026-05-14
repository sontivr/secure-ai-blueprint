"""
Test configuration and shared fixtures.

Module-level code (env vars + sys.modules stubs) MUST run before any backend
import, because config.py and auth.py both raise RuntimeError at import time
when required env vars are absent, and rag_pipeline.py / pdf_utils.py pull in
chromadb, sentence-transformers, and pdfplumber which are not installed in the
test environment.
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Pre-compute PBKDF2 hashes for known test credentials (stdlib only).
#    Uses a fixed salt so the values are deterministic across runs.
# ---------------------------------------------------------------------------

def _pbkdf2_hash(password: str) -> str:
    salt = b"\x01" * 16
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000, dklen=32)
    s64 = base64.urlsafe_b64encode(salt).decode().rstrip("=")
    d64 = base64.urlsafe_b64encode(dk).decode().rstrip("=")
    return f"pbkdf2_sha256$200000${s64}${d64}"


# ---------------------------------------------------------------------------
# 2. Set required env vars BEFORE any backend module is imported.
# ---------------------------------------------------------------------------

os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-testing-minimum-32-chars")
os.environ.setdefault("ADMIN_PASSWORD_HASH", _pbkdf2_hash("admin123"))
os.environ.setdefault("USER_PASSWORD_HASH", _pbkdf2_hash("user123"))

# ---------------------------------------------------------------------------
# 3. Stub heavy third-party packages so the backend imports cleanly without
#    chromadb / sentence-transformers / pdfplumber being installed.
# ---------------------------------------------------------------------------

for _mod in ("chromadb", "chromadb.config", "sentence_transformers", "pdfplumber"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---------------------------------------------------------------------------
# 4. Fixtures
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from unittest.mock import patch  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _make_mock_store() -> MagicMock:
    store = MagicMock()
    store.client.heartbeat.return_value = None
    store.upsert_text.return_value = {"upserted": 3}
    store.upsert_pages.return_value = {"upserted": 2}
    store.query.return_value = [
        {
            "id": "doc:abc123",
            "source": "policy.txt",
            "page": None,
            "chunk_index": 0,
            "distance": 0.5,
            "text": "The policy requires annual review.",
        }
    ]
    return store


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear per-IP rate-limit counters between tests."""
    from backend.main import _reset_login_counters
    _reset_login_counters()
    yield
    _reset_login_counters()


@pytest.fixture
def mock_store() -> MagicMock:
    return _make_mock_store()


@pytest.fixture
def client(mock_store: MagicMock):
    with (
        patch("backend.main.store", mock_store),
        patch("backend.main.ollama_chat", return_value="Answer:\nGrounded answer.\n\nEvidence:\n- policy.txt"),
        patch("backend.main.write_audit"),
    ):
        from backend.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture
def admin_token(client: TestClient) -> str:
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def user_token(client: TestClient) -> str:
    resp = client.post("/auth/login", json={"username": "user", "password": "user123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
