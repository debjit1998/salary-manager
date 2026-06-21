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

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2048

INSTRUCTIONS = (
    "You are a query assistant for ACME's HR analytics tool. The user "
    "is an HR manager.\n\n"
    "When asked a question, prefer ONE of the structured analytics "
    "tools — they cover headcount, average/median salary, salary "
    "distribution, top earners, comp band ratios, raises in a "
    "period, and headcount changes. Pick the most specific tool for "
    "the question.\n\n"
    "Only call `execute_sql` as a LAST RESORT when no structured tool "
    "fits. Examples that REQUIRE execute_sql: questions about specific "
    "employees by name, manager-chain navigation, cohort comparisons "
    "across multiple dimensions, equity-grant totals.\n\n"
    "For currency: salaries are stored natively but the "
    "employees_current_salary view exposes `amount_usd`. Default to USD "
    "unless the user asks for native currency.\n\n"
    "Default status to 'active' unless the user explicitly mentions "
    "terminated employees.\n\n"
    "If you genuinely cannot answer with the data available, say so "
    "briefly in plain text — do NOT invent values."
)


_client: Anthropic | None = None


def get_client() -> Anthropic:
    """Lazy-initialised Anthropic client. Raises if the key is missing."""
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set; NL query feature disabled"
            )
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
