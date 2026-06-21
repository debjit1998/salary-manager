"""Unit tests for the NL endpoint's SQL guard.

The guard is the first line of defence around the `execute_sql`
last-resort tool. Failures here would let the LLM bypass the read-only
role (defence in depth still holds, but we want this guard to catch
the obvious cases at the AST level).
"""

from __future__ import annotations

import pytest

from app.src.nl.sql_guard import MAX_ROWS, SqlGuardError, validate_select


# --- Happy paths --------------------------------------------------------


def test_valid_select_passes_through() -> None:
    out = validate_select("SELECT id FROM employees WHERE country = 'US'")
    assert "SELECT" in out.upper()
    assert "LIMIT" in out.upper()


def test_limit_added_when_absent() -> None:
    out = validate_select("SELECT * FROM employees")
    assert f"LIMIT {MAX_ROWS}" in out


def test_limit_capped_at_max() -> None:
    out = validate_select("SELECT * FROM employees LIMIT 99999")
    assert f"LIMIT {MAX_ROWS}" in out
    assert "99999" not in out


def test_small_limit_preserved() -> None:
    out = validate_select("SELECT * FROM employees LIMIT 10")
    assert "LIMIT 10" in out


def test_select_with_cte_passes() -> None:
    sql = """
        WITH active AS (SELECT id FROM employees WHERE status = 'active')
        SELECT count(*) FROM active
    """
    out = validate_select(sql)
    assert "active" in out.lower()


def test_trailing_semicolon_stripped() -> None:
    out = validate_select("SELECT 1;")
    assert "SELECT" in out.upper()


# --- DML / DDL must be rejected -----------------------------------------


@pytest.mark.parametrize(
    "stmt",
    [
        "DELETE FROM employees",
        "UPDATE employees SET status = 'terminated'",
        "INSERT INTO employees (id) VALUES ('x')",
        "DROP TABLE employees",
        "CREATE TABLE foo (id int)",
        "ALTER TABLE employees ADD COLUMN x text",
        "TRUNCATE employees",
    ],
)
def test_dml_ddl_rejected(stmt: str) -> None:
    with pytest.raises(SqlGuardError):
        validate_select(stmt)


def test_multiple_statements_rejected() -> None:
    with pytest.raises(SqlGuardError, match="single statements"):
        validate_select("SELECT 1; SELECT 2")


def test_select_followed_by_delete_rejected() -> None:
    """The classic SQL injection trail. sqlglot should see both statements."""
    with pytest.raises(SqlGuardError):
        validate_select("SELECT 1; DELETE FROM employees")


# --- Forbidden functions -----------------------------------------------


@pytest.mark.parametrize(
    "stmt",
    [
        "SELECT pg_sleep(5)",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_ls_dir('/')",
    ],
)
def test_forbidden_functions_rejected(stmt: str) -> None:
    with pytest.raises(SqlGuardError, match="forbidden function"):
        validate_select(stmt)


# --- Garbage -----------------------------------------------------------


def test_empty_string_rejected() -> None:
    with pytest.raises(SqlGuardError):
        validate_select("")


def test_unparseable_rejected() -> None:
    with pytest.raises(SqlGuardError):
        validate_select("SELEKT * FROM nope WHERE")
