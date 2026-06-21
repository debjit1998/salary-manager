"""Shared Pydantic models used by more than one domain.

Domain-specific request / response models stay in their domain folder
(`employee/schemas.py`, `analytics/schemas.py`, etc.). This file only
holds models that genuinely cross domain boundaries.
"""

from __future__ import annotations

from pydantic import BaseModel

from .enums import (
    BandPosition,
    Country,
    EmployeeStatus,
    EmploymentType,
)


class EmployeeFilters(BaseModel):
    """Standard set of employee filters shared by the analytics
    endpoints and the dashboard's per-chart filter dialogs.

    Every field is a LIST (multi-select). None / empty list = no filter.
    A missing `status` is treated as `['active']` inside the where-
    clause builder — the dashboard nearly always wants active rows.

    `salary_band` and `band_position` only work when the query JOINs
    `employees_current_salary` (alias `ecs`) and `comp_bands`
    (alias `cb`); the analytics functions JOIN them by default so all
    seven filters work uniformly."""

    country: list[Country] | None = None
    department_id: list[int] | None = None
    level_id: list[int] | None = None
    employment_type: list[EmploymentType] | None = None
    status: list[EmployeeStatus] | None = None
    salary_band: list[str] | None = None
    band_position: list[BandPosition] | None = None
