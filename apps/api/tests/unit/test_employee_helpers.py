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
#
# Multi-select aware: every filter takes a LIST of values. The SQL emits
# `column = ANY(:bind)` and psycopg adapts Python lists to Postgres
# ARRAY[...] automatically.


def test_build_filters_empty_returns_empty_clause() -> None:
    where, params = build_filters()
    assert where == ""
    assert params == {}


def test_build_filters_search_query_lowercases_and_wraps_with_wildcards() -> None:
    where, params = build_filters(q="Alice")
    assert "lower(e.first_name || ' ' || e.last_name) LIKE :q" in where
    assert "OR lower(e.email) LIKE :q" in where
    assert params == {"q": "%alice%"}


def test_build_filters_single_value_list_uses_ANY() -> None:
    where, params = build_filters(country=["UK"])
    assert "e.country = ANY(:country)" in where
    assert params == {"country": ["UK"]}


def test_build_filters_multi_value_list() -> None:
    where, params = build_filters(country=["UK", "IN", "US"])
    assert "e.country = ANY(:country)" in where
    assert params == {"country": ["UK", "IN", "US"]}


def test_build_filters_multiple_conditions_joined_with_AND() -> None:
    where, params = build_filters(country=["UK"], level_id=[4])
    assert "e.country = ANY(:country)" in where
    assert "e.level_id = ANY(:level_id)" in where
    assert " AND " in where
    assert params == {"country": ["UK"], "level_id": [4]}


def test_build_filters_all_filters() -> None:
    where, params = build_filters(
        q="Bob",
        dept_id=[1],
        country=["US"],
        level_id=[4],
        employment_type=["full_time"],
        status=["active"],
        band_position=["within"],
    )
    assert set(params.keys()) == {
        "q",
        "dept_id",
        "country",
        "level_id",
        "employment_type",
        "status",
        "band_position",
    }
    # Seven conditions = six ANDs in the joined string
    assert where.count(" AND ") == 6


def test_build_filters_none_and_empty_lists_are_excluded() -> None:
    """`None` means filter not set; `[]` means filter explicitly empty.
    Both are dropped from the WHERE clause — emitting `= ANY(ARRAY[])`
    would match no rows, which isn't what the caller meant.
    """
    where, params = build_filters(country=["US"], dept_id=None, level_id=[])
    assert "country" in params
    assert "dept_id" not in params
    assert "level_id" not in params


def test_build_filters_band_position_uses_case_expression() -> None:
    """band_position is the one filter whose condition isn't a simple
    column reference — it CASE-expressions against ecs/cb columns that
    the caller's FROM clause must provide.
    """
    where, params = build_filters(band_position=["below", "above"])
    assert "CASE" in where
    assert "ecs.amount IS NULL OR cb.band_min IS NULL" in where
    assert "= ANY(:band_position)" in where
    assert params == {"band_position": ["below", "above"]}
