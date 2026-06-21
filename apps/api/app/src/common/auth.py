"""Authentication primitives — password hashing, JWT, and the
get_current_user FastAPI dependency.

All routes that require auth depend on `get_current_user`, which:
  1. Reads the `session` httpOnly cookie set by /auth/login.
  2. Decodes the JWT and validates the signature + expiry.
  3. Looks up the user row by id (a deleted user shouldn't keep a
     valid session even if the JWT is still in date).
  4. Raises 401 on any failure.

Password hashing uses bcrypt (12 rounds) directly — no passlib. The
JWT library is PyJWT.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.settings import settings

COOKIE_NAME = "session"


# --- Password hashing -----------------------------------------------------


def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())


# --- JWT encode / decode --------------------------------------------------


def create_jwt(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# --- Dependency: the user object handed to protected routes --------------


class CurrentUser(BaseModel):
    id: str
    email: str


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> CurrentUser:
    """FastAPI dependency. Raises 401 if the session cookie is missing,
    invalid, expired, or refers to a user that no longer exists.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _unauthorized("not authenticated")

    try:
        payload = decode_jwt(token)
        user_id = payload["sub"]
    except (jwt.PyJWTError, KeyError):
        raise _unauthorized("invalid or expired session")

    row = (
        session.execute(
            text("SELECT id, email FROM users WHERE id = :id"),
            {"id": user_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise _unauthorized("user no longer exists")

    return CurrentUser(id=str(row["id"]), email=row["email"])


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Cookie"},
    )
