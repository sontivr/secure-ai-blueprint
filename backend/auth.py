from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from jose import jwt, JWTError

from .config import JWT_SECRET, JWT_ALG, JWT_EXPIRES_MIN

# ---- PBKDF2 helpers (stdlib; no bcrypt/passlib needed) ----

_PBKDF2_ITERS = 200_000
_SALT_BYTES = 16
_DKLEN = 32

def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))

def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS, dklen=_DKLEN)
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${_b64e(salt)}${_b64e(dk)}"

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters_s, salt_b64, dk_b64 = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64d(salt_b64)
        expected = _b64d(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters, dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False

# ---- Lean V1: in-memory users (replace with DB/IdP later) ----
import os

ADMIN_HASH = os.getenv("ADMIN_PASSWORD_HASH")
USER_HASH = os.getenv("USER_PASSWORD_HASH")

if not ADMIN_HASH or not USER_HASH:
    raise RuntimeError("ADMIN_PASSWORD_HASH and USER_PASSWORD_HASH must be set")

_USERS = {
    "admin": {"password_hash": ADMIN_HASH, "role": "admin"},
    "user": {"password_hash": USER_HASH, "role": "user"},
}

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    u = _USERS.get(username)
    if not u:
        return None
    if not verify_password(password, u["password_hash"]):
        return None
    return {"username": username, "role": u["role"]}

def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRES_MIN)
    payload = {"sub": subject, "role": role, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> Dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError as e:
        raise ValueError("Invalid token") from e
