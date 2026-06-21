"""Pydantic schemas for the analytics endpoints.

Each tool has a dedicated request + response model. The same schemas
are reused by the NL-query endpoint (Task #8) when Claude picks a tool.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.src.common.enums import (
    BandPosition,
    Country,
    Dimension,
    SalaryReason,
)
from app.src.common.schemas import EmployeeFilters

# Re-export so analytics consumers can keep the existing import paths
# working (the router imports EmployeeFilters from .schemas).
__all__ = [
    "AvgSalaryByResult",
    "AvgSalaryByRow",
    "BandSummary",
    "CompRatioVsBandResult",
    "DistributionBucket",
    "EmployeeFilters",
    "HeadcountByResult",
    "HeadcountByRow",
    "HeadcountChangeRequest",
    "HeadcountChangeResult",
    "HeadcountChangeRow",
    "OutOfBandEmployee",
    "RaiseEvent",
    "RaisesInPeriodRequest",
    "RaisesInPeriodResult",
    "SalaryDistributionResult",
    "SummaryResult",
    "TopEarner",
    "TopEarnersRequest",
    "TopEarnersResult",
]


# --- summary -------------------------------------------------------------


class SummaryResult(BaseModel):
    """KPI tiles for the dashboard top row."""

    active_headcount: int
    avg_salary_usd: Decimal
    below_band_count: int
    hires_last_90_days: int


# --- headcount_by --------------------------------------------------------


class HeadcountByRow(BaseModel):
    dimension: str
    count: int


class HeadcountByResult(BaseModel):
    rows: list[HeadcountByRow]
    dimension: Dimension
    total: int


# --- avg_salary_by -------------------------------------------------------


class AvgSalaryByRow(BaseModel):
    dimension: str
    avg_salary_usd: Decimal
    median_salary_usd: Decimal
    count: int


class AvgSalaryByResult(BaseModel):
    rows: list[AvgSalaryByRow]
    dimension: Dimension


# --- salary_distribution -------------------------------------------------


class DistributionBucket(BaseModel):
    label: str
    lower_usd: int
    upper_usd: int | None  # None for the topmost open-ended bucket
    count: int


class SalaryDistributionResult(BaseModel):
    buckets: list[DistributionBucket]
    total: int


# --- top_n_earners -------------------------------------------------------


class TopEarner(BaseModel):
    id: str
    employee_no: str
    first_name: str
    last_name: str
    country: Country
    department: str
    level: str
    amount_usd: Decimal
    amount_native: Decimal
    currency_code: str


class TopEarnersResult(BaseModel):
    rows: list[TopEarner]


# --- comp_ratio_vs_band --------------------------------------------------


class BandSummary(BaseModel):
    below: int
    within: int
    above: int


class OutOfBandEmployee(BaseModel):
    id: str
    employee_no: str
    first_name: str
    last_name: str
    country: Country
    department: str
    level: str
    amount: Decimal
    currency_code: str
    band_min: Decimal
    band_max: Decimal
    band_position: BandPosition


class CompRatioVsBandResult(BaseModel):
    summary: BandSummary
    out_of_band: list[OutOfBandEmployee]


# --- raises_in_period ----------------------------------------------------


class RaiseEvent(BaseModel):
    id: str
    employee_id: str
    employee_no: str
    first_name: str
    last_name: str
    country: Country
    department: str
    level: str
    effective_date: date
    amount: Decimal
    currency_code: str
    amount_usd: Decimal
    reason: SalaryReason
    note: str | None


class RaisesInPeriodResult(BaseModel):
    rows: list[RaiseEvent]
    count: int
    start: date
    end: date


# --- headcount_change ----------------------------------------------------


class HeadcountChangeRow(BaseModel):
    dimension: str
    before_start: int
    hired_in_period: int
    total_through_end: int


class HeadcountChangeResult(BaseModel):
    rows: list[HeadcountChangeRow]
    dimension: Dimension
    start: date
    end: date


# --- Request bodies (POST endpoints for the more complex inputs) ---------


class RaisesInPeriodRequest(BaseModel):
    start: date
    end: date
    filters: EmployeeFilters = Field(default_factory=EmployeeFilters)


class HeadcountChangeRequest(BaseModel):
    start: date
    end: date
    dimension: Dimension


class TopEarnersRequest(BaseModel):
    n: int = Field(default=10, ge=1, le=100)
    filters: EmployeeFilters = Field(default_factory=EmployeeFilters)
