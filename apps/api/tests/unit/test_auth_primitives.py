"""Unit tests for the auth primitives — bcrypt + JWT helpers.

No DB, no FastAPI, no fixtures. Just pure-function I/O. The point is
to isolate "is the crypto/JWT logic correct?" from "is the login
endpoint wired up correctly?" — different concerns, different tests.

These run in milliseconds with no docker stack required.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.settings import settings
from app.src.common.auth import (
    create_jwt,
    decode_jwt,
    hash_password,
    verify_password,
)


def test_hash_then_verify_roundtrip() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)


def test_verify_password_wrong_password_returns_false() -> None:
    h = hash_password("hunter2")
    assert verify_password("wrong-password", h) is False


def test_hash_password_uses_random_salt() -> None:
    """Same plaintext should hash to different strings — proves bcrypt
    is generating a fresh salt each call.
    """
    assert hash_password("x") != hash_password("x")


def test_jwt_roundtrip_carries_sub_and_dates() -> None:
    token = create_jwt("user-123")
    payload = decode_jwt(token)
    assert payload["sub"] == "user-123"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_jwt_expired_raises_expired_signature() -> None:
    """Manually mint an expired JWT and verify decode_jwt rejects it."""
    expired = jwt.encode(
        {
            "sub": "user-123",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_jwt(expired)


def test_jwt_tampered_signature_rejected() -> None:
    token = create_jwt("user-123")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_jwt(tampered)


def test_jwt_wrong_secret_rejected() -> None:
    """A token signed with a different secret must not be accepted by
    our decoder — basic signature-validation sanity.
    """
    token = jwt.encode(
        {
            "sub": "user-123",
            "exp": int(
                (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
            ),
        },
        "completely-different-secret",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_jwt(token)


def test_jwt_wrong_algorithm_rejected() -> None:
    """If someone tries to swap to HS512 we should reject it (we only
    accept the configured algorithm)."""
    token = jwt.encode(
        {
            "sub": "user-123",
            "exp": int(
                (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
            ),
        },
        settings.jwt_secret,
        algorithm="HS512",
    )
    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_jwt(token)
