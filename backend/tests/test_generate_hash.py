import re

import pytest

from backend import generate_hash

HASH_REGEX = re.compile(r"^pbkdf2_sha256\$\d+\$[A-Za-z0-9_-]+\$[A-Za-z0-9_-]+$")


def test_hash_format():
    """Generated hash should follow the expected pbkdf2_sha256 format."""
    h = generate_hash.hash_password("secret123")
    assert HASH_REGEX.match(h), f"Unexpected hash format: {h}"


def test_hash_uniqueness():
    """Hashes for the same password should differ due to random salt."""
    h1 = generate_hash.hash_password("password")
    h2 = generate_hash.hash_password("password")
    assert h1 != h2


def test_salt_and_dk_lengths():
    """Salt and derived key portions should decode to expected lengths."""
    h = generate_hash.hash_password("hello")
    parts = h.split("$")
    assert parts[0] == "pbkdf2_sha256"
    iters = int(parts[1])
    assert iters == 200_000

    salt_b64 = parts[2]
    dk_b64 = parts[3]

    # restore padding for base64 decoding
    pad = "=" * (-len(salt_b64) % 4)
    salt = __import__("base64").urlsafe_b64decode(salt_b64 + pad)
    assert len(salt) == generate_hash._SALT_BYTES

    pad = "=" * (-len(dk_b64) % 4)
    dk = __import__("base64").urlsafe_b64decode(dk_b64 + pad)
    assert len(dk) == generate_hash._DKLEN
