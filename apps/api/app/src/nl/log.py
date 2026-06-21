"""Writes one row to `nl_query_log` per NL request.

The table is append-only — feeds an admin view (not yet built) for
auditing the feature in production. Failures here MUST NOT propagate
to the user response: we log and swallow."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def write_log(
    session: Session,
    *,
    user_id: str | None,
    question: str,
    tool_picked: str | None,
    tool_args: dict[str, Any] | None,
    sql_emitted: str | None,
    result_rows: int | None,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    error: str | None,
) -> None:
    try:
        session.execute(
            text(
                """
                INSERT INTO nl_query_log
                  (user_id, question, tool_picked, tool_args, sql_emitted,
                   result_rows, latency_ms, input_tokens, output_tokens, error)
                VALUES
                  (:user_id, :question, :tool, :args, :sql, :rows,
                   :latency, :input_tok, :output_tok, :error)
                """
            ),
            {
                "user_id": user_id,
                "question": question,
                "tool": tool_picked,
                "args": json.dumps(tool_args) if tool_args is not None else None,
                "sql": sql_emitted,
                "rows": result_rows,
                "latency": latency_ms,
                "input_tok": input_tokens,
                "output_tok": output_tokens,
                "error": error,
            },
        )
        session.commit()
    except Exception:  # noqa: BLE001
        # The user request has already succeeded by the time we get here;
        # don't fail it because logging fell over.
        log.exception("failed to write nl_query_log")
        session.rollback()
