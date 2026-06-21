"""Pydantic schemas for the lookups endpoint.

`CurrencyRow` is deliberately named to avoid clashing with the Literal
`Currency` (the set of supported codes) from `common.enums`. The FE's
`types/api.ts` already uses `CurrencyRow` for this shape.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class Department(BaseModel):
    id: int
    name: str


class Level(BaseModel):
    id: int
    code: str
    rank: int


class CurrencyRow(BaseModel):
    """One row of the `currencies` reference table."""

    code: str
    name: str
    ratio_to_usd: Decimal


class LookupsResponse(BaseModel):
    departments: list[Department]
    levels: list[Level]
    currencies: list[CurrencyRow]
