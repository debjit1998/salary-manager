"""POST /nl-query — natural-language HR analytics endpoint.

Pipeline:

    question
      → Anthropic (system + cached schema + tools)
        → either a `tool_use` block...
            → dispatch to the matching ToolSpec.dispatch
        → ...or plain text (model couldn't / refused)
      → log to nl_query_log
      → response
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

from anthropic import APIError, BadRequestError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import engine, get_session
from app.settings import settings
from app.src.common.auth import CurrentUser, get_current_user

from .client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    build_system,
    get_client,
)
from .schemas import (
    NLErrorResponse,
    NLMeta,
    NLQueryRequest,
    NLSqlResponse,
    NLTextResponse,
    NLToolResponse,
)
from .log import write_log
from .schema_prompt import build_schema_prompt
from .sql_guard import SqlGuardError
from .tools import TOOL_DEFINITIONS, TOOL_DISPATCH

log = logging.getLogger(__name__)

router = APIRouter(prefix="/nl-query", tags=["nl"])


# --- Cached schema description -------------------------------------------
#
# Built once on first request (lazy so app startup doesn't require the
# DB to be reachable, and so tests can patch the engine before the
# block is built). Reset on app restart, which is every deploy.

_schema_block: str | None = None


def get_schema_block() -> str:
    global _schema_block
    if _schema_block is None:
        _schema_block = build_schema_prompt(engine)
    return _schema_block


# --- Anthropic content helpers -------------------------------------------


def _find_tool_use(content: list[Any]) -> Any | None:
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            return block
    return None


def _join_text(content: list[Any]) -> str:
    return "".join(
        getattr(b, "text", "") for b in content if getattr(b, "type", None) == "text"
    ).strip()


# --- Endpoint -------------------------------------------------------------


@router.post(
    "",
    response_model=NLToolResponse | NLSqlResponse | NLTextResponse | NLErrorResponse,
)
def nl_query(
    body: NLQueryRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NL feature disabled: ANTHROPIC_API_KEY not set",
        )

    started = time.perf_counter()
    today = date.today().isoformat()
    user_message = f"Today is {today}.\n\nQuestion: {body.question}"

    try:
        client = get_client()
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=build_system(get_schema_block()),
            tools=TOOL_DEFINITIONS,
            messages=[{"role": "user", "content": user_message}],
        )
    except BadRequestError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            error=f"anthropic 400: {exc}",
            latency_ms=latency_ms,
        )
        raise HTTPException(status_code=502, detail="upstream model error") from exc
    except APIError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            error=f"anthropic error: {exc}",
            latency_ms=latency_ms,
        )
        raise HTTPException(status_code=502, detail="upstream model error") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = response.usage
    meta = NLMeta(
        latency_ms=latency_ms,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )

    tool_block = _find_tool_use(response.content)

    if tool_block is None:
        # The model returned plain text — log and return as-is.
        text = _join_text(response.content) or "I couldn't answer that with the data I have."
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return NLTextResponse(kind="text", text=text, meta=meta)

    tool_name = tool_block.name
    tool_args = dict(tool_block.input or {})

    dispatch = TOOL_DISPATCH.get(tool_name)
    if dispatch is None:
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            error=f"unknown tool: {tool_name}",
            tool_picked=tool_name,
            tool_args=tool_args,
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return NLErrorResponse(kind="error", error=f"unknown tool: {tool_name}", meta=meta)

    try:
        result = dispatch(session, tool_args)
    except SqlGuardError as exc:
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            tool_picked=tool_name,
            tool_args=tool_args,
            sql_emitted=str(tool_args.get("sql", "")),
            error=f"sql_guard: {exc}",
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return NLErrorResponse(kind="error", error=f"unsafe SQL: {exc}", meta=meta)
    except Exception as exc:  # noqa: BLE001
        log.exception("tool dispatch failed: %s", tool_name)
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            tool_picked=tool_name,
            tool_args=tool_args,
            error=f"dispatch failure: {exc}",
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return NLErrorResponse(kind="error", error=f"tool failed: {exc}", meta=meta)

    if tool_name == "execute_sql":
        rows = result["rows"]
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            tool_picked=tool_name,
            tool_args=tool_args,
            sql_emitted=result["sql"],
            result_rows=len(rows),
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return NLSqlResponse(
            kind="sql",
            sql=result["sql"],
            columns=result["columns"],
            rows=rows,
            meta=meta,
        )

    _log_safe(
        session,
        user_id=user.id,
        question=body.question,
        tool_picked=tool_name,
        tool_args=tool_args,
        result_rows=_count_rows(result),
        latency_ms=latency_ms,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    return NLToolResponse(kind="tool", tool=tool_name, args=tool_args, result=result, meta=meta)


# --- Helpers --------------------------------------------------------------


def _count_rows(result: Any) -> int | None:
    """Best-effort row count for the nl_query_log audit row."""
    if isinstance(result, dict):
        for key in ("rows", "out_of_band", "buckets"):
            if key in result and isinstance(result[key], list):
                return len(result[key])
    return None


def _log_safe(session: Session, **kwargs: Any) -> None:
    """write_log with sensible defaults for the optional fields, so each
    error path doesn't need to spell them all out."""
    defaults: dict[str, Any] = {
        "user_id": None,
        "question": "",
        "tool_picked": None,
        "tool_args": None,
        "sql_emitted": None,
        "result_rows": None,
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "error": None,
    }
    defaults.update(kwargs)
    write_log(session, **defaults)
