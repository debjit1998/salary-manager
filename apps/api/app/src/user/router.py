"""Authentication routes: login, logout, me.

Cookie-based session: on successful login we set an httpOnly cookie
holding a JWT. The frontend never sees the token; logout deletes the
cookie.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.settings import settings
from app.src.common.auth import (
    COOKIE_NAME,
    CurrentUser,
    create_jwt,
    get_current_user,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr


@router.post("/login", response_model=UserOut)
def login(
    body: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    row = (
        session.execute(
            text("SELECT id, email, password_hash FROM users WHERE email = :email"),
            {"email": body.email.lower()},
        )
        .mappings()
        .one_or_none()
    )

    # Same error message for unknown email and wrong password — leaks
    # less information about which emails exist.
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )

    token = create_jwt(str(row["id"]))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )
    return UserOut(id=str(row["id"]), email=row["email"])


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser = Depends(get_current_user)) -> UserOut:
    return UserOut(id=current_user.id, email=current_user.email)
