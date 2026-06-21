"""Anthropic tool definitions for the NL endpoint.

Eight tools total:
  - 7 thin wrappers over `app.src.analytics.queries.*` — Claude picks
    one of these for any HR question the analytics layer can answer.
  - `execute_sql` — last-resort fallback. Claude generates a single
    SELECT; the backend validates it via `sql_guard.validate_select`
    and executes against the read-only `nl_readonly` Postgres role.

Each tool entry has:
  - `definition`: JSON Schema given to Anthropic so Claude can call it
  - `dispatch`:   Python callable (session, args) -> result dict
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.src.analytics import queries as analytics_q
from app.src.common.schemas import EmployeeFilters

from .sql_guard import SqlGuardError, validate_select

# ---- Reusable JSON-Schema fragments --------------------------------------

_FILTERS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "Optional employee filters. Status defaults to 'active'.",
    "properties": {
        "country": {
            "type": "string",
            "enum": ["US", "UK", "IN"],
            "description": "ISO-2 country code.",
        },
        "department_id": {"type": "integer"},
        "level_id": {"type": "integer"},
        "employment_type": {
            "type": "string",
            "enum": ["full_time", "part_time", "contractor"],
        },
        "status": {
            "type": "string",
            "enum": ["active", "terminated"],
            "default": "active",
        },
    },
}

_DIMENSION_ENUM = ["department", "level", "country", "employment_type"]


def _filters_from(args: dict[str, Any]) -> EmployeeFilters:
    return EmployeeFilters(**(args.get("filters") or {}))


# ---- Per-tool dispatchers ------------------------------------------------


def _headcount_by(session: Session, args: dict[str, Any]) -> dict:
    return analytics_q.headcount_by(
        session, dimension=args["dimension"], filters=_filters_from(args)
    )


def _avg_salary_by(session: Session, args: dict[str, Any]) -> dict:
    return analytics_q.avg_salary_by(
        session, dimension=args["dimension"], filters=_filters_from(args)
    )


def _salary_distribution(session: Session, args: dict[str, Any]) -> dict:
    return analytics_q.salary_distribution(session, filters=_filters_from(args))


def _top_n_earners(session: Session, args: dict[str, Any]) -> dict:
    return analytics_q.top_n_earners(
        session,
        n=int(args.get("n", 10)),
        filters=_filters_from(args),
    )


def _comp_ratio_vs_band(session: Session, args: dict[str, Any]) -> dict:
    return analytics_q.comp_ratio_vs_band(session, filters=_filters_from(args))


def _raises_in_period(session: Session, args: dict[str, Any]) -> dict:
    return analytics_q.raises_in_period(
        session,
        start=args["start"],
        end=args["end"],
        filters=_filters_from(args),
    )


def _headcount_change(session: Session, args: dict[str, Any]) -> dict:
    return analytics_q.headcount_change(
        session,
        start=args["start"],
        end=args["end"],
        dimension=args["dimension"],
    )


def _execute_sql(session: Session, args: dict[str, Any]) -> dict:
    """Last-resort tool. Validates the SQL via sql_guard, then runs it on
    a read-only Postgres role inside a 10-second-timeout transaction."""
    safe_sql = validate_select(str(args.get("sql", "")))
    # SAVEPOINT — the per-test SAVEPOINT pattern means we can't use a
    # nested transaction; `SET LOCAL` here applies to the outer txn and
    # is rolled back on commit/rollback. Both effects fade outside this
    # function.
    session.execute(text("SET LOCAL ROLE nl_readonly"))
    session.execute(text("SET LOCAL statement_timeout = '10s'"))
    try:
        result = session.execute(text(safe_sql))
        cols = list(result.keys())
        rows = [dict(r._mapping) for r in result]
    finally:
        # Restore the calling role; the timeout reset is automatic on
        # transaction end but we don't want the role stuck in the pool.
        session.execute(text("RESET ROLE"))
        session.execute(text("RESET statement_timeout"))
    return {"sql": safe_sql, "columns": cols, "rows": rows}


# ---- Tool catalogue ------------------------------------------------------

ToolDispatch = Callable[[Session, dict[str, Any]], dict]


class ToolSpec:
    __slots__ = ("name", "definition", "dispatch")

    def __init__(
        self,
        name: str,
        definition: dict[str, Any],
        dispatch: ToolDispatch,
    ) -> None:
        self.name = name
        self.definition = definition
        self.dispatch = dispatch


TOOLS: list[ToolSpec] = [
    ToolSpec(
        "headcount_by",
        {
            "name": "headcount_by",
            "description": (
                "Count of active employees grouped by one dimension. Use for "
                "questions like 'how many employees do we have per "
                "department?', 'how many people in each country?', or "
                "'headcount by level'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "dimension": {
                        "type": "string",
                        "enum": _DIMENSION_ENUM,
                        "description": "What to group by.",
                    },
                    "filters": _FILTERS_SCHEMA,
                },
                "required": ["dimension"],
            },
        },
        _headcount_by,
    ),
    ToolSpec(
        "avg_salary_by",
        {
            "name": "avg_salary_by",
            "description": (
                "Average and median salary (in USD) grouped by one "
                "dimension. Returns rows of (dimension, avg_salary_usd, "
                "median_salary_usd, count). Use for 'average salary per "
                "level', 'median pay by department', etc."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "dimension": {
                        "type": "string",
                        "enum": _DIMENSION_ENUM,
                    },
                    "filters": _FILTERS_SCHEMA,
                },
                "required": ["dimension"],
            },
        },
        _avg_salary_by,
    ),
    ToolSpec(
        "salary_distribution",
        {
            "name": "salary_distribution",
            "description": (
                "Histogram of current salaries in USD. Returns fixed "
                "buckets: 0-50k, 50-100k, 100-150k, 150-200k, 200-300k, "
                "300-500k, 500k+. Use for 'salary distribution' or "
                "'spread of pay across the company'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"filters": _FILTERS_SCHEMA},
            },
        },
        _salary_distribution,
    ),
    ToolSpec(
        "top_n_earners",
        {
            "name": "top_n_earners",
            "description": (
                "Top N employees by current salary (USD). Use for 'who "
                "are our top earners', 'top 20 by salary in UK', etc."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                    },
                    "filters": _FILTERS_SCHEMA,
                },
            },
        },
        _top_n_earners,
    ),
    ToolSpec(
        "comp_ratio_vs_band",
        {
            "name": "comp_ratio_vs_band",
            "description": (
                "Counts of employees below / within / above their "
                "comp band, plus the list of out-of-band employees. Use "
                "for 'who is below band', 'how many people are paid above "
                "band in engineering', etc."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"filters": _FILTERS_SCHEMA},
            },
        },
        _comp_ratio_vs_band,
    ),
    ToolSpec(
        "raises_in_period",
        {
            "name": "raises_in_period",
            "description": (
                "Salary raises and promotions whose effective date falls "
                "within [start, end]. Use for 'raises in Q1', 'who got "
                "promoted last year', 'how many raises happened in the "
                "last 90 days', etc."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "format": "date"},
                    "end": {"type": "string", "format": "date"},
                    "filters": _FILTERS_SCHEMA,
                },
                "required": ["start", "end"],
            },
        },
        _raises_in_period,
    ),
    ToolSpec(
        "headcount_change",
        {
            "name": "headcount_change",
            "description": (
                "Headcount before period / hired during period / total "
                "through end-date, grouped by one dimension. Use for "
                "'how did the team grow in 2025', 'headcount change by "
                "department this year', etc."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "format": "date"},
                    "end": {"type": "string", "format": "date"},
                    "dimension": {"type": "string", "enum": _DIMENSION_ENUM},
                },
                "required": ["start", "end", "dimension"],
            },
        },
        _headcount_change,
    ),
    ToolSpec(
        "execute_sql",
        {
            "name": "execute_sql",
            "description": (
                "LAST-RESORT. Generate a single SELECT against the "
                "database when no other tool fits. The SQL is parsed "
                "and validated (single SELECT, no DML/DDL), executed "
                "against a read-only role with a 10-second timeout and "
                "a forced LIMIT 1000. PREFER the structured tools "
                "above whenever they can answer the question."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A single SELECT statement, no semicolons, "
                            "no DML/DDL."
                        ),
                    },
                },
                "required": ["sql"],
            },
        },
        _execute_sql,
    ),
]

TOOL_DEFINITIONS: list[dict[str, Any]] = [t.definition for t in TOOLS]
TOOL_DISPATCH: dict[str, ToolDispatch] = {t.name: t.dispatch for t in TOOLS}
