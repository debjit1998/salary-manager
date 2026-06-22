"""One-step self-correcting agent loop for the NL endpoint.

Pipeline:

    question
      → messages.create   (system + cached schema + tools + user)
        → tool_use(execute_sql, sql=...)
            → dispatch
                → success → return SQL result
                → error   → push tool_result with is_error=true
                            → messages.create again (attempt #2)
                                → dispatch
                                    → success → return SQL result
                                    → error   → return error to caller
      → text response (no tool_use) → return as-is, no retry

Retry rules:
  - Max 1 retry (so worst case is 2 Anthropic round trips).
  - Retry on sql_guard rejections (e.g. accidental DML) AND on
    real Postgres errors raised inside the tool. Both are things
    Claude can self-correct from given the error message.
  - Do NOT retry on text-only responses, unknown-tool picks, or
    Anthropic API errors — none of those would change on a re-ask
    with the same conversation.

Anthropic API errors (BadRequestError, APIError) are NOT caught here —
they propagate to the router so it can convert them to HTTP 502.

Logging stays in the router. The agent returns telemetry in AgentResult;
the router writes one nl_query_log row reflecting the final outcome.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from anthropic import Anthropic
from sqlalchemy.orm import Session

from .client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    build_system,
)
from .sql_guard import SqlGuardError
from .tools import TOOL_DEFINITIONS, TOOL_DISPATCH

log = logging.getLogger(__name__)

# Tool error strings shipped back to Claude can include the entire
# offending SQL — useful, but also bloats the next input. Cap it.
_MAX_TOOL_ERROR_CHARS = 800


AgentKind = Literal[
    "sql",  # execute_sql tool ran successfully
    "tool",  # other tool ran successfully (none today)
    "text",  # Claude returned plain text instead of a tool call
    "guard_error",  # sqlglot guard rejected the SQL on every attempt
    "tool_error",  # tool raised on every attempt (e.g. Postgres error)
    "unknown_tool",  # Claude picked a tool not in our catalogue
]


@dataclass
class AgentResult:
    kind: AgentKind

    # Telemetry — always set, summed across attempts when retried.
    attempts: int = 1
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    # Tool-related (kind in {"sql", "tool"})
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None

    # Text-only (kind == "text")
    text: str | None = None

    # Error-related (kind in {"guard_error", "tool_error", "unknown_tool"})
    error: str | None = None
    # On retried errors, also keep the SQL emitted on the FINAL attempt
    # so the log row records what actually failed (not the original try).
    sql_emitted: str | None = None


def _find_tool_use(content: list[Any]) -> Any | None:
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            return block
    return None


def _join_text(content: list[Any]) -> str:
    return "".join(
        getattr(b, "text", "") for b in content if getattr(b, "type", None) == "text"
    ).strip()


def _accumulate_usage(target: AgentResult, usage: Any) -> None:
    target.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
    target.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
    target.cache_read_tokens += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    target.cache_creation_tokens += int(getattr(usage, "cache_creation_input_tokens", 0) or 0)


def _truncate(s: str, limit: int = _MAX_TOOL_ERROR_CHARS) -> str:
    return s if len(s) <= limit else s[: limit - 1] + "…"


def run_agent(
    *,
    client: Anthropic,
    session: Session,
    question: str,
    schema_block: str,
    max_attempts: int = 2,
) -> AgentResult:
    """Run the NL → SQL agent loop with at most `max_attempts - 1` retries.

    Returns an AgentResult describing the final outcome plus accumulated
    telemetry (latency + tokens across all Anthropic calls). The router
    converts the result into one of the NL*Response Pydantic models and
    writes one nl_query_log row.
    """
    started = time.perf_counter()

    system = build_system(schema_block)
    user_message = f"Today is {date.today().isoformat()}.\n\nQuestion: {question}"
    conversation: list[dict[str, Any]] = [
        {"role": "user", "content": user_message},
    ]

    result = AgentResult(kind="tool_error", attempts=0)
    last_error: str | None = None
    last_sql: str | None = None

    for attempt in range(1, max_attempts + 1):
        result.attempts = attempt

        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=conversation,
        )
        _accumulate_usage(result, response.usage)

        tool_block = _find_tool_use(response.content)

        if tool_block is None:
            # Plain-text answer. No retry — same prompt would give the
            # same refusal/clarification.
            result.kind = "text"
            result.text = (
                _join_text(response.content) or "I couldn't answer that with the data I have."
            )
            break

        tool_name = tool_block.name
        tool_args = dict(tool_block.input or {})
        result.tool_name = tool_name
        result.tool_args = tool_args
        last_sql = str(tool_args.get("sql", "")) or None

        dispatch = TOOL_DISPATCH.get(tool_name)
        if dispatch is None:
            # Unknown tool — not retryable. Same prompt won't recover.
            result.kind = "unknown_tool"
            result.error = f"unknown tool: {tool_name}"
            result.sql_emitted = last_sql
            break

        try:
            tool_payload = dispatch(session, tool_args)
            # Success.
            result.kind = "sql" if tool_name == "execute_sql" else "tool"
            result.tool_result = tool_payload
            result.sql_emitted = (
                tool_payload.get("sql") if isinstance(tool_payload, dict) else None
            ) or last_sql
            result.error = None
            break

        except SqlGuardError as exc:
            last_error = f"unsafe SQL: {exc}"
            result.kind = "guard_error"
            result.error = last_error
            result.sql_emitted = last_sql

        except Exception as exc:  # noqa: BLE001
            log.exception("tool dispatch failed: %s", tool_name)
            last_error = f"tool failed: {exc}"
            result.kind = "tool_error"
            result.error = last_error
            result.sql_emitted = last_sql

        # We only get here on a retryable error. If we have attempts
        # left, ship the error back to Claude as a tool_result so it
        # can self-correct.
        if attempt < max_attempts:
            conversation.append({"role": "assistant", "content": response.content})
            conversation.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": _truncate(last_error or "tool failed"),
                            "is_error": True,
                        }
                    ],
                }
            )
            continue

        # Out of attempts — final error stays in result.
        break

    result.latency_ms = int((time.perf_counter() - started) * 1000)
    return result
