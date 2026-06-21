"""Unit tests for the schema-prompt renderer.

Validates the merge of introspection + hints — no DB required for the
pure functions; we hand-construct Table objects.
"""

from __future__ import annotations

import pytest

from app.src.nl.schema_prompt import (
    Column,
    SchemaHintError,
    Table,
    render,
    validate_hints,
)


def _sample_tables() -> dict[str, Table]:
    return {
        "employees": Table(
            name="employees",
            kind="table",
            columns=[
                Column("id", "uuid", nullable=False),
                Column("country", "character", nullable=False),
                Column("manager_id", "uuid", nullable=True, fk=("employees", "id")),
            ],
        ),
        "employees_current_salary": Table(
            name="employees_current_salary",
            kind="view",
            columns=[
                Column("employee_id", "uuid", nullable=False),
                Column("amount_usd", "numeric", nullable=True),
            ],
        ),
    }


# --- validate_hints -----------------------------------------------------


def test_validate_hints_passes_on_known_tables() -> None:
    validate_hints(
        _sample_tables(),
        {
            "employees": {
                "columns": {"country": "ISO-2"},
                "notes": ["primary directory"],
            },
            "employees_current_salary": {"kind": "view"},
        },
    )


def test_validate_hints_rejects_unknown_table() -> None:
    with pytest.raises(SchemaHintError, match="unknown table"):
        validate_hints(_sample_tables(), {"ghost_table": {}})


def test_validate_hints_rejects_unknown_column() -> None:
    with pytest.raises(SchemaHintError, match="unknown column"):
        validate_hints(
            _sample_tables(),
            {"employees": {"columns": {"ghost_column": "noop"}}},
        )


def test_validate_hints_accepts_empty_hint_block() -> None:
    """A table key with no `columns` or `notes` is valid — sometimes
    you want to anchor it in the YAML for future edits."""
    validate_hints(_sample_tables(), {"employees": None})


# --- render -------------------------------------------------------------


def test_render_includes_table_and_view_keywords() -> None:
    out = render(_sample_tables(), {})
    assert "TABLE employees" in out
    assert "VIEW employees_current_salary" in out


def test_render_includes_fk_arrows() -> None:
    out = render(_sample_tables(), {})
    assert "manager_id" in out
    assert "→ employees.id" in out


def test_render_attaches_string_column_hint() -> None:
    hints = {"employees": {"columns": {"country": "ISO-2 country code"}}}
    out = render(_sample_tables(), hints)
    assert "country: character  -- ISO-2 country code" in out


def test_render_attaches_dict_column_hint_with_values() -> None:
    hints = {
        "employees": {
            "columns": {
                "country": {
                    "description": "ISO-2 country code",
                    "values": ["US", "UK", "IN"],
                }
            }
        }
    }
    out = render(_sample_tables(), hints)
    assert "ISO-2 country code" in out
    assert "values: US, UK, IN" in out


def test_render_appends_notes() -> None:
    hints = {"employees": {"notes": ["primary directory", "filter by status"]}}
    out = render(_sample_tables(), hints)
    assert "NOTE: primary directory" in out
    assert "NOTE: filter by status" in out
