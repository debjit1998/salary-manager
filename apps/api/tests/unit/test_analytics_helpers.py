"""Unit tests for the pure helpers in app.src.analytics.queries.

Exercises the dimension whitelist and the WHERE-clause builder — both
are pure functions with no DB dependency.
"""

from __future__ import annotations

import pytest

from app.src.analytics.queries import (
    _DIMENSION_SPEC,
    _build_employee_where,
    _dimension,
)
from app.src.analytics.schemas import EmployeeFilters


# --- _dimension ----------------------------------------------------------


@pytest.mark.parametrize("name", sorted(_DIMENSION_SPEC.keys()))
def test_dimension_known_returns_spec(name: str) -> None:
    spec = _dimension(name)
    assert "select" in spec
    assert "group_by" in spec
    assert "order_by" in spec


def test_dimension_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unsupported dimension"):
        _dimension("password")


# --- _build_employee_where ----------------------------------------------


def test_where_default_filters_to_active_only() -> None:
    where, params = _build_employee_where(None)
    assert where == "e.status = :status"
    assert params == {"status": "active"}


def test_where_includes_country() -> None:
    where, params = _build_employee_where(EmployeeFilters(country="UK"))
    assert "e.country = :country" in where
    assert params == {"status": "active", "country": "UK"}


def test_where_includes_all_filters_with_AND() -> None:
    where, params = _build_employee_where(
        EmployeeFilters(
            country="US",
            department_id=1,
            level_id=4,
            employment_type="full_time",
            status="active",
        )
    )
    # 5 conditions => 4 ANDs in the joined string
    assert where.count(" AND ") == 4
    assert set(params.keys()) == {
        "status",
        "country",
        "department_id",
        "level_id",
        "employment_type",
    }


def test_where_status_terminated_is_passed_through() -> None:
    where, params = _build_employee_where(EmployeeFilters(status="terminated"))
    assert params["status"] == "terminated"


def test_where_alias_override() -> None:
    where, _ = _build_employee_where(EmployeeFilters(country="US"), alias="emp")
    assert "emp.country = :country" in where
    assert "emp.status = :status" in where
