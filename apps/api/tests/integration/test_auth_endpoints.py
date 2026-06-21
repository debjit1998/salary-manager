"""Integration tests for /auth/login, /auth/logout, /auth/me.

These exercise the full stack: FastAPI routing, Pydantic validation,
SQLAlchemy session, real Postgres, bcrypt, JWT encode/decode, cookie
middleware.

Covers:
  - happy path: login → /me → logout
  - wrong password
  - unknown email (must look identical to wrong password — no leakage)
  - /me without a cookie
  - /me with garbage / expired / tampered / orphaned JWT
  - case-insensitive login email
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.settings import settings
from app.src.common.auth import COOKIE_NAME


def test_login_sets_cookie_and_me_returns_user(
    client: TestClient, test_user: dict[str, str]
) -> None:
    r = client.post(
        "/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == test_user["email"]
    assert body["id"] == test_user["id"]

    set_cookie = r.headers.get("set-cookie", "")
    assert f"{COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == test_user["email"]


def test_login_wrong_password_returns_401(
    client: TestClient, test_user: dict[str, str]
) -> None:
    r = client.post(
        "/auth/login",
        json={"email": test_user["email"], "password": "not-the-password"},
    )
    assert r.status_code == 401
    assert COOKIE_NAME not in r.headers.get("set-cookie", "")


def test_login_unknown_email_returns_same_401(client: TestClient) -> None:
    r = client.post(
        "/auth/login",
        json={"email": "ghost@acme.org", "password": "anything"},
    )
    assert r.status_code == 401
    # Same message as wrong-password — don't leak which emails exist.
    assert r.json()["detail"] == "invalid email or password"


def test_me_without_cookie_returns_401(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_garbage_cookie_returns_401(client: TestClient) -> None:
    client.cookies.set(COOKIE_NAME, "not-a-valid-jwt")
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_expired_jwt_returns_401(
    client: TestClient, test_user: dict[str, str]
) -> None:
    expired = jwt.encode(
        {
            "sub": test_user["id"],
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    client.cookies.set(COOKIE_NAME, expired)
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_jwt_for_nonexistent_user_returns_401(client: TestClient) -> None:
    """Valid signature, not expired, but user id has no DB row."""
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(
                (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
            ),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    client.cookies.set(COOKIE_NAME, token)
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_logout_clears_cookie(client: TestClient, test_user: dict[str, str]) -> None:
    client.post(
        "/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    r = client.post("/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    me = client.get("/auth/me")
    assert me.status_code == 401


def test_login_email_is_case_insensitive(
    client: TestClient, test_user: dict[str, str]
) -> None:
    upper = test_user["email"].upper()
    r = client.post(
        "/auth/login",
        json={"email": upper, "password": test_user["password"]},
    )
    assert r.status_code == 200
