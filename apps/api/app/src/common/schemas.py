"""Shared Pydantic models used by more than one domain.

Domain-specific request / response models stay in their domain folder
(`employee/schemas.py`, `analytics/schemas.py`, etc.). This file only
holds models that genuinely cross domain boundaries.
"""

from __future__ import annotations

from pydantic import BaseModel

from .enums import Country, EmployeeStatus, EmploymentType


class EmployeeFilters(BaseModel):
    """Standard set of employee filters shared by the analytics tools
    and the NL endpoint's tool dispatcher. None on each field means
    "no filter on this dimension"; status defaults to 'active' because
    that's what the dashboard cares about by default."""

    country: Country | None = None
    department_id: int | None = None
    level_id: int | None = None
    employment_type: EmploymentType | None = None
    status: EmployeeStatus = "active"
