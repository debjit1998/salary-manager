"""Anthropic client + system prompt building.

The system prompt has two text blocks:

    [0]  fixed instructions (about a paragraph)
    [1]  the auto-derived schema description — marked
         `cache_control: {"type": "ephemeral"}` so it lives in
         Anthropic's prompt cache. Cache TTL is ~5 minutes; cache hits
         show up in response.usage.cache_read_input_tokens.

Today's date and the user question are passed in the user message, NOT
the system prompt — keeps the cache key stable across requests.
"""

from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from app.settings import settings

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 2048

INSTRUCTIONS = (
    "You are a query assistant for ACME's HR analytics tool. The user "
    "is an HR manager.\n\n"
    "Use the `execute_sql` tool to answer the user's question with a "
    "single read-only SELECT. The query is parsed and validated, runs "
    "against a read-only Postgres role with a 10-second timeout, and "
    "is force-LIMITed to 1000 rows. There is no other tool — every "
    "question is answered by writing SQL.\n\n"
    "HARD RULES (the backend's sqlglot guard rejects violations — wasted "
    "round-trip):\n"
    "  - Emit ONE SELECT. No DML (INSERT/UPDATE/DELETE/MERGE), no DDL "
    "(CREATE/ALTER/DROP/TRUNCATE), no SET / RESET / SET LOCAL / GRANT / "
    "REVOKE / BEGIN / COMMIT / ROLLBACK / SAVEPOINT / LOCK / COPY. Role "
    "and timeout are managed by the backend — don't touch them.\n"
    "  - PERCENTILE_CONT always returns double precision (not numeric), "
    "so `ROUND(PERCENTILE_CONT(…), 2)` fails. Cast first: "
    "`ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x)::numeric, 2)`. "
    "Same trap for any other aggregate that returns float.\n\n"
    "WRITING GOOD SQL:\n"
    "  - Use the table + view definitions in the schema below; pay "
    "attention to NOTE lines (e.g. 'prefer the employees_current_"
    "salary view over raw salary_changes').\n"
    "  - The REFERENCE DATA blocks under departments, levels, and "
    "currencies give you the integer ids and FX rates. Use them "
    "directly — don't subquery to look up an id by name when you "
    "already have the mapping.\n"
    "  - Default `status = 'active'` unless the user explicitly asks "
    "about terminated employees.\n"
    "  - Default amounts to USD via `amount_usd` from "
    "employees_current_salary. If the user asks for a specific currency "
    "('in pounds', 'in INR'), convert: amount_in_target = amount_usd * "
    "ratio_to_usd where ratio_to_usd comes from the currencies table.\n"
    "  - Aggregations: use COUNT(*), AVG, percentile_cont(0.5) WITHIN "
    "GROUP for median, etc. GROUP BY when the user asks for a "
    "breakdown.\n"
    "  - For 'top N' questions, ORDER BY amount_usd DESC LIMIT N.\n"
    "  - For salary thresholds ('over $X', 'above £Y'), use a WHERE "
    "clause on amount_usd (or the converted amount).\n"
    "  - For below/within/above band, JOIN comp_bands on "
    "(level_id, country) and compare ecs.amount to cb.band_min/band_max "
    "in the row's native currency.\n\n"
    "If you genuinely cannot answer with the data available, say so "
    "briefly in plain text — do NOT invent values."
)


_client: Anthropic | None = None


def get_client() -> Anthropic:
    """Lazy-initialised Anthropic client. Raises if the key is missing."""
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; NL query feature disabled")
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def build_system(schema_block: str) -> list[dict[str, Any]]:
    """The system-prompt array for `messages.create`. The schema block
    gets `cache_control` so it lives in Anthropic's ephemeral cache."""
    return [
        {"type": "text", "text": INSTRUCTIONS},
        {
            "type": "text",
            "text": schema_block,
            "cache_control": {"type": "ephemeral"},
        },
    ]
