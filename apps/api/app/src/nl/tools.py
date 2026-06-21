"""Anthropic tool definitions for the NL endpoint.

One tool only: `execute_sql`. Claude generates a single SELECT; the
backend validates it via `sql_guard.validate_select` and executes
against the read-only `nl_readonly` Postgres role.

Why only one tool: we tried a hybrid design (7 structured analytics
wrappers + this SQL escape hatch) and found that the LLM occasionally
picked a "close-enough" structured tool when the question actually
needed a custom filter the tool didn't expose. Routing every question
through SQL trades that source of error for a different one (LLM-
generated SQL can be wrong), but every question is now answered with
the same well-tested guard rails:

  - sqlglot AST validation (single SELECT, no DML/DDL, no dangerous funcs)
  - `nl_readonly` Postgres role (SELECT-only grants, defence in depth)
  - 10-second statement_timeout
  - Forced LIMIT 1000

The structured analytics functions in `app.src.analytics.queries` are
unchanged — they still power the `/analytics/*` REST endpoints used by
the dashboard panels. They're just not exposed to the LLM anymore.
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from .sql_guard import validate_select


def _execute_sql(session: Session, args: dict[str, Any]) -> dict:
    """Validate the SQL via sql_guard, then run it on the read-only
    `nl_readonly` Postgres role with a 10-second statement_timeout."""
    safe_sql = validate_select(str(args.get("sql", "")))
    session.execute(text("SET LOCAL ROLE nl_readonly"))
    session.execute(text("SET LOCAL statement_timeout = '10s'"))
    try:
        result = session.execute(text(safe_sql))
        cols = list(result.keys())
        rows = [dict(r._mapping) for r in result]
    finally:
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
        "execute_sql",
        {
            "name": "execute_sql",
            "description": (
                "Run a read-only SELECT against the HR database to "
                "answer the user's question. The query is parsed and "
                "validated (single SELECT, no DML/DDL, no dangerous "
                "functions), executed against a read-only Postgres "
                "role with a 10-second timeout and a forced LIMIT 1000. "
                "Use the schema and reference data inlined in the "
                "system prompt to write accurate joins."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A single SELECT statement, no semicolons, "
                            "no DML/DDL. Reference the schema below "
                            "for column names and the REFERENCE DATA "
                            "blocks for department/level/currency ids."
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
