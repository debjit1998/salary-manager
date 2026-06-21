"""Pydantic schemas for the employee endpoints.

Kept in a separate module because the in/out surface is larger than the
auth module — splitting makes it easier to spot what the API returns
without reading endpoint code.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# --- Enums (Literal aliases mirror the DB CHECK constraints) -------------

Country = Literal["US", "UK", "IN"]
Currency = Literal["USD", "GBP", "INR"]
EmploymentType = Literal["full_time", "part_time", "contractor"]
EmployeeStatus = Literal["active", "terminated"]
SalaryReason = Literal["hire", "raise", "promo", "adjustment"]
BandPosition = Literal["below", "within", "above"]


# --- Nested response objects ---------------------------------------------


class CurrentSalary(BaseModel):
    amount: Decimal
    currency_code: str
    amount_usd: Decimal
    effective_date: date


class SalaryChangeOut(BaseModel):
    id: str
    effective_date: date
    amount: Decimal
    currency_code: str
    amount_usd: Decimal
    reason: SalaryReason
    note: str | None
    created_at: date


class EquityGrantOut(BaseModel):
    id: str
    grant_date: date
    shares: int
    created_at: date


class ManagerSummary(BaseModel):
    id: str
    employee_no: str
    first_name: str
    last_name: str


# --- List endpoint -------------------------------------------------------


class EmployeeListItem(BaseModel):
    id: str
    employee_no: str
    first_name: str
    last_name: str
    email: EmailStr
    country: Country
    department: str
    level: str
    employment_type: EmploymentType
    status: EmployeeStatus
    hire_date: date
    manager_id: str | None
    current_salary: CurrentSalary | None
    band_position: BandPosition | None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeListItem]
    page: int
    size: int
    total: int


# --- Detail endpoint -----------------------------------------------------


class EmployeeDetail(BaseModel):
    id: str
    employee_no: str
    first_name: str
    last_name: str
    email: EmailStr
    country: Country
    department_id: int
    department: str
    level_id: int
    level: str
    employment_type: EmploymentType
    status: EmployeeStatus
    hire_date: date
    manager: ManagerSummary | None
    direct_reports_count: int
    current_salary: CurrentSalary | None
    band_position: BandPosition | None
    total_shares: int
    salary_changes: list[SalaryChangeOut]
    equity_grants: list[EquityGrantOut]


# --- Update / write endpoints --------------------------------------------


class EmployeeUpdate(BaseModel):
    """All fields optional — PATCH semantics."""

    department_id: int | None = None
    level_id: int | None = None
    manager_id: str | None = None
    employment_type: EmploymentType | None = None
    status: EmployeeStatus | None = None


class SalaryChangeCreate(BaseModel):
    effective_date: date
    amount: Decimal = Field(gt=0)
    currency_code: Currency
    reason: SalaryReason
    note: str | None = None


class EquityGrantCreate(BaseModel):
    grant_date: date
    shares: int = Field(gt=0)
