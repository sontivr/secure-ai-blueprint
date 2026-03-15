import os
import base64
import hashlib
import hmac

_PBKDF2_ITERS = 200_000
_SALT_BYTES = 16
_DKLEN = 32

def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERS,
        dklen=_DKLEN,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${_b64e(salt)}${_b64e(dk)}"

if __name__ == "__main__":
    pwd = input("Enter password: ")
    print("\nGenerated hash:\n")
    print(hash_password(pwd))
