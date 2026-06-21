"""Unit tests for the pure helpers in app.src.employee.queries.

These have no DB / FastAPI dependency — they exercise the sort parser
and the filter builder, both of which are the only injection-surface
parts of the dynamic SQL build path.
"""

from __future__ import annotations

import pytest

from app.src.employee.queries import ALLOWED_SORTS, build_filters, parse_sort


# --- parse_sort ----------------------------------------------------------


def test_parse_sort_default_is_employee_no_asc() -> None:
    column, direction = parse_sort(None)
    assert column == ALLOWED_SORTS["employee_no"]
    assert direction == "ASC"


def test_parse_sort_empty_string_returns_default() -> None:
    column, direction = parse_sort("")
    assert column == ALLOWED_SORTS["employee_no"]
    assert direction == "ASC"


def test_parse_sort_ascending_key() -> None:
    column, direction = parse_sort("hire_date")
    assert column == ALLOWED_SORTS["hire_date"]
    assert direction == "ASC"


def test_parse_sort_descending_prefix() -> None:
    column, direction = parse_sort("-current_salary_usd")
    assert column == ALLOWED_SORTS["current_salary_usd"]
    assert direction == "DESC"


def test_parse_sort_unknown_key_raises() -> None:
    with pytest.raises(ValueError, match="unsupported sort key"):
        parse_sort("password")


def test_parse_sort_descending_unknown_key_raises() -> None:
    """A descending prefix on an unknown key must still raise — guards
    against e.g. `-; DROP TABLE` slipping through if the prefix were
    handled too leniently.
    """
    with pytest.raises(ValueError):
        parse_sort("-foo_bar")


# --- build_filters -------------------------------------------------------


def test_build_filters_empty_returns_empty_clause() -> None:
    where, params = build_filters()
    assert where == ""
    assert params == {}


def test_build_filters_search_query_lowercases_and_wraps_with_wildcards() -> None:
    where, params = build_filters(q="Alice")
    assert "lower(e.first_name || ' ' || e.last_name) LIKE :q" in where
    assert "OR lower(e.email) LIKE :q" in where
    assert params == {"q": "%alice%"}


def test_build_filters_multiple_conditions_joined_with_AND() -> None:
    where, params = build_filters(country="UK", level_id=4)
    # Order matters because we rely on it for the joined string
    assert "e.country = :country" in where
    assert "e.level_id = :level_id" in where
    assert " AND " in where
    assert params == {"country": "UK", "level_id": 4}


def test_build_filters_all_filters() -> None:
    where, params = build_filters(
        q="Bob",
        dept_id=1,
        country="US",
        level_id=4,
        employment_type="full_time",
        status="active",
    )
    assert set(params.keys()) == {
        "q",
        "dept_id",
        "country",
        "level_id",
        "employment_type",
        "status",
    }
    # Six conditions = five ANDs in the joined string
    assert where.count(" AND ") == 5


def test_build_filters_none_values_are_excluded() -> None:
    where, params = build_filters(country="US", dept_id=None, level_id=None)
    assert "country" in params
    assert "dept_id" not in params
    assert "level_id" not in params
