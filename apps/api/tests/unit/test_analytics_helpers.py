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
from app.src.common.schemas import EmployeeFilters

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
    """No filter → status pinned to 'active' inline (no bind param)."""
    where, params = _build_employee_where(None)
    assert "e.status = 'active'" in where
    assert params == {}


def test_where_includes_country_list() -> None:
    where, params = _build_employee_where(EmployeeFilters(country=["UK"]))
    assert "e.country = ANY(:country)" in where
    assert params == {"country": ["UK"]}


def test_where_country_multi_select() -> None:
    where, params = _build_employee_where(EmployeeFilters(country=["US", "UK"]))
    assert "e.country = ANY(:country)" in where
    assert params == {"country": ["US", "UK"]}


def test_where_includes_all_scalar_filters_with_AND() -> None:
    where, params = _build_employee_where(
        EmployeeFilters(
            country=["US"],
            department_id=[1],
            level_id=[4],
            employment_type=["full_time"],
            status=["active"],
        )
    )
    # 5 conditions → 4 ANDs
    assert where.count(" AND ") == 4
    assert set(params.keys()) == {
        "status",
        "country",
        "department_id",
        "level_id",
        "employment_type",
    }


def test_where_status_explicit_is_passed_through() -> None:
    where, params = _build_employee_where(EmployeeFilters(status=["terminated"]))
    assert "e.status = ANY(:status)" in where
    assert params["status"] == ["terminated"]


def test_where_status_empty_list_falls_back_to_active() -> None:
    """An empty list is treated like 'no filter' — defaults to active."""
    where, params = _build_employee_where(EmployeeFilters(status=[]))
    assert "e.status = 'active'" in where
    assert "status" not in params


def test_where_alias_override() -> None:
    where, _ = _build_employee_where(EmployeeFilters(country=["US"]), alias="emp")
    assert "emp.country = ANY(:country)" in where
    assert "emp.status = 'active'" in where


def test_where_salary_band_uses_case_expression() -> None:
    """salary_band is a synthetic filter — a CASE over ecs.amount_usd."""
    where, params = _build_employee_where(
        EmployeeFilters(salary_band=["100000-150000", "150000-200000"])
    )
    assert "CASE" in where
    assert "ecs.amount_usd" in where
    assert "= ANY(:salary_band)" in where
    assert params["salary_band"] == ["100000-150000", "150000-200000"]


def test_where_band_position_uses_case_expression() -> None:
    where, params = _build_employee_where(EmployeeFilters(band_position=["below", "above"]))
    assert "CASE" in where
    assert "cb.band_min" in where
    assert "= ANY(:band_position)" in where
    assert params["band_position"] == ["below", "above"]
