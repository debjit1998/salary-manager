"""Pydantic schemas for the NL-query endpoint.

The endpoint can return one of four discriminated-union shapes (see
`NLResponse`). The frontend dispatches rendering on `kind`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .client import DEFAULT_MODEL


class NLQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class NLMeta(BaseModel):
    """Per-request observability. NOT rendered in the UI; used for
    logging + debugging + the prompt-cache hit indicator."""

    latency_ms: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    model: str = DEFAULT_MODEL
    # Number of Anthropic round trips used to answer this question.
    # 1 = first try succeeded; 2 = first tool call errored, Claude
    # self-corrected on the retry. See `llm_agent.run_agent`.
    attempts: int = 1


class NLToolResponse(BaseModel):
    """Claude picked one of the structured analytics tools. `result`
    is the typed dict that the matching analytics function returned;
    the FE dispatches on `tool` to pick the right viz."""

    kind: Literal["tool"]
    tool: str
    args: dict[str, Any]
    result: Any
    meta: NLMeta


class NLSqlResponse(BaseModel):
    """Claude called `execute_sql` and the sqlglot guard let the query
    through. `sql` is the post-guard string (LIMIT may have been
    added); `columns` + `rows` are the raw result set."""

    kind: Literal["sql"]
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    meta: NLMeta


class NLTextResponse(BaseModel):
    """Claude returned plain text instead of a tool call — either it
    refused or it couldn't answer."""

    kind: Literal["text"]
    text: str
    meta: NLMeta


class NLErrorResponse(BaseModel):
    """Known failure mode (unsafe SQL, unknown tool, dispatch
    exception). HTTP status is still 200 — these are expected outcomes
    of the feature, not server bugs."""

    kind: Literal["error"]
    error: str
    meta: NLMeta


NLResponse = NLToolResponse | NLSqlResponse | NLTextResponse | NLErrorResponse
