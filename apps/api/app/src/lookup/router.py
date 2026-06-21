"""Reference-data lookup endpoint.

Returns departments, levels, and currencies in one round-trip — the
frontend caches the whole bundle for the session, so filter dropdowns,
form selects, and currency labels don't each need their own endpoint.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.src.common.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/lookups", tags=["lookups"])


class Department(BaseModel):
    id: int
    name: str


class Level(BaseModel):
    id: int
    code: str
    rank: int


class Currency(BaseModel):
    code: str
    name: str
    ratio_to_usd: Decimal


class LookupsResponse(BaseModel):
    departments: list[Department]
    levels: list[Level]
    currencies: list[Currency]


@router.get("", response_model=LookupsResponse)
def get_lookups(
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> LookupsResponse:
    depts = session.execute(
        text("SELECT id, name FROM departments ORDER BY name")
    ).mappings().all()
    levels = session.execute(
        text("SELECT id, code, rank FROM levels ORDER BY rank")
    ).mappings().all()
    currencies = session.execute(
        text("SELECT code, name, ratio_to_usd FROM currencies ORDER BY code")
    ).mappings().all()
    return LookupsResponse(
        departments=[Department(**dict(r)) for r in depts],
        levels=[Level(**dict(r)) for r in levels],
        currencies=[Currency(**dict(r)) for r in currencies],
    )
