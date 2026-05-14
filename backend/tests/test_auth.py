import pytest

from backend.auth import (
    authenticate_user,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_roundtrip(self):
        h = hash_password("mysecret")
        assert verify_password("mysecret", h) is True

    def test_wrong_password_rejected(self):
        h = hash_password("correct")
        assert verify_password("wrongpassword", h) is False

    def test_different_passwords_produce_different_hashes(self):
        assert hash_password("abc") != hash_password("abc")

    def test_tampered_hash_rejected(self):
        h = hash_password("secret")
        tampered = h[:-4] + "XXXX"
        assert verify_password("secret", tampered) is False

    def test_malformed_hash_rejected(self):
        assert verify_password("any", "not-a-valid-hash") is False

    def test_wrong_scheme_rejected(self):
        assert verify_password("any", "bcrypt$whatever$salt$dk") is False


class TestTokens:
    def test_roundtrip(self):
        token = create_access_token(subject="alice", role="admin")
        payload = decode_token(token)
        assert payload["sub"] == "alice"
        assert payload["role"] == "admin"

    def test_payload_contains_iat_and_exp(self):
        token = create_access_token(subject="bob", role="user")
        payload = decode_token(token)
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("this.is.not.a.valid.jwt")

    def test_tampered_token_raises(self):
        token = create_access_token(subject="eve", role="user")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(ValueError):
            decode_token(tampered)


class TestAuthenticateUser:
    # Credentials match what conftest.py sets in ADMIN_PASSWORD_HASH / USER_PASSWORD_HASH

    def test_admin_correct_credentials(self):
        user = authenticate_user("admin", "admin123")
        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "admin"

    def test_user_correct_credentials(self):
        user = authenticate_user("user", "user123")
        assert user is not None
        assert user["username"] == "user"
        assert user["role"] == "user"

    def test_wrong_password_returns_none(self):
        assert authenticate_user("admin", "wrongpass") is None

    def test_unknown_user_returns_none(self):
        assert authenticate_user("nobody", "anypass") is None

    def test_empty_username_returns_none(self):
        assert authenticate_user("", "admin123") is None
