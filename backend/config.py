import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root (secure-ai-blueprint/.env)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma")))
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", str(DATA_DIR / "audit.jsonl")))

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-.env")
JWT_ALG = "HS256"
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "480"))  # 8 hours by default

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

APP_NAME = "Secure AI Blueprint (Lean V1)"
ENV = os.getenv("ENV", "dev")

ANONYMIZED_TELEMETRY = os.getenv("ANONYMIZED_TELEMETRY", "False").lower() == "true"

MAX_RETRIEVAL_DISTANCE = float(os.getenv("MAX_RETRIEVAL_DISTANCE", "1.2"))
