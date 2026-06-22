"""POST /nl-query — natural-language HR analytics endpoint.

The actual LLM + tool loop lives in `llm_agent.run_agent`. This router
is the HTTP/translation layer: validate the request, run the agent,
log the outcome to nl_query_log, and shape the response into one of
the NL*Response Pydantic schemas the frontend dispatches on.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from anthropic import APIError, BadRequestError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import engine, get_session
from app.settings import settings
from app.src.common.auth import CurrentUser, get_current_user

from .client import get_client
from .llm_agent import AgentResult, run_agent
from .log import write_log
from .schema_prompt import build_schema_prompt
from .schemas import (
    NLErrorResponse,
    NLMeta,
    NLQueryRequest,
    NLSqlResponse,
    NLTextResponse,
    NLToolResponse,
)

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
    try:
        result = run_agent(
            client=get_client(),
            session=session,
            question=body.question,
            schema_block=get_schema_block(),
        )
    except BadRequestError as exc:
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            error=f"anthropic 400: {exc}",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        raise HTTPException(status_code=502, detail="upstream model error") from exc
    except APIError as exc:
        _log_safe(
            session,
            user_id=user.id,
            question=body.question,
            error=f"anthropic error: {exc}",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        raise HTTPException(status_code=502, detail="upstream model error") from exc

    meta = NLMeta(
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_creation_tokens=result.cache_creation_tokens,
        attempts=result.attempts,
    )

    return _shape_response(session, user, body.question, result, meta)


# --- Response shaping + logging ------------------------------------------


def _shape_response(
    session: Session,
    user: CurrentUser,
    question: str,
    result: AgentResult,
    meta: NLMeta,
):
    """Translate the AgentResult into the matching NL*Response and write
    a single nl_query_log row reflecting the final outcome."""

    if result.kind == "text":
        _log_safe(
            session,
            user_id=user.id,
            question=question,
            latency_ms=meta.latency_ms,
            input_tokens=meta.input_tokens,
            output_tokens=meta.output_tokens,
        )
        return NLTextResponse(kind="text", text=result.text or "", meta=meta)

    if result.kind == "unknown_tool":
        _log_safe(
            session,
            user_id=user.id,
            question=question,
            error=result.error,
            tool_picked=result.tool_name,
            tool_args=result.tool_args,
            latency_ms=meta.latency_ms,
            input_tokens=meta.input_tokens,
            output_tokens=meta.output_tokens,
        )
        return NLErrorResponse(kind="error", error=result.error or "unknown tool", meta=meta)

    if result.kind in {"guard_error", "tool_error"}:
        _log_safe(
            session,
            user_id=user.id,
            question=question,
            tool_picked=result.tool_name,
            tool_args=result.tool_args,
            sql_emitted=result.sql_emitted,
            error=result.error,
            latency_ms=meta.latency_ms,
            input_tokens=meta.input_tokens,
            output_tokens=meta.output_tokens,
        )
        return NLErrorResponse(kind="error", error=result.error or "tool failed", meta=meta)

    # Successful tool dispatch.
    payload = result.tool_result or {}

    if result.kind == "sql":
        rows = payload.get("rows", [])
        _log_safe(
            session,
            user_id=user.id,
            question=question,
            tool_picked=result.tool_name,
            tool_args=result.tool_args,
            sql_emitted=payload.get("sql"),
            result_rows=len(rows),
            latency_ms=meta.latency_ms,
            input_tokens=meta.input_tokens,
            output_tokens=meta.output_tokens,
        )
        return NLSqlResponse(
            kind="sql",
            sql=payload.get("sql", ""),
            columns=payload.get("columns", []),
            rows=rows,
            meta=meta,
        )

    # kind == "tool" — generic structured-tool result. Today there's no
    # such tool registered, but keep the branch for future tools.
    _log_safe(
        session,
        user_id=user.id,
        question=question,
        tool_picked=result.tool_name,
        tool_args=result.tool_args,
        result_rows=_count_rows(payload),
        latency_ms=meta.latency_ms,
        input_tokens=meta.input_tokens,
        output_tokens=meta.output_tokens,
    )
    return NLToolResponse(
        kind="tool",
        tool=result.tool_name or "",
        args=result.tool_args or {},
        result=payload,
        meta=meta,
    )


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
