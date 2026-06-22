"""Integration tests for POST /nl-query.

Anthropic is fully mocked — we don't make real API calls during tests.
The dispatch + logging + error-handling pipeline is what these tests
cover; sql_guard and schema_prompt have their own unit tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


def _usage(
    *,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read: int = 0,
    cache_create: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_create,
    )


def _tool_use_block(
    name: str, args: dict[str, Any], block_id: str = "toolu_test"
) -> SimpleNamespace:
    # Real Anthropic responses always include `id` on tool_use blocks;
    # the agent needs it to thread tool_result back on retry.
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=args)


def _text_block(text_: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text_)


def _response(content: list[Any], usage: SimpleNamespace | None = None) -> SimpleNamespace:
    return SimpleNamespace(content=content, usage=usage or _usage())


@pytest.fixture
def fake_anthropic(monkeypatch: pytest.MonkeyPatch):
    """Patches the `get_client` symbol AS BOUND IN THE ROUTER MODULE
    so calls in the endpoint route through our fake — `from .client
    import get_client` creates a local binding that patching the
    `client` module alone wouldn't reach. Also stubs the API-key check
    and the cached schema block.

    Returns a setter you can call with either:
      - a single response object → reused for every Anthropic call
      - a list of response objects → consumed one per call (for the
        agent's retry path)
    """
    from app.settings import settings
    from app.src.nl import router as nl_router

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key", raising=False)
    monkeypatch.setattr(nl_router, "_schema_block", "TEST_SCHEMA_BLOCK", raising=False)

    state: dict[str, Any] = {"response": None, "calls": 0}

    class _FakeMessages:
        def create(self, **_kw):
            state["calls"] += 1
            r = state["response"]
            if isinstance(r, list):
                if not r:
                    raise RuntimeError("fake_anthropic: response queue exhausted")
                return r.pop(0)
            return r

    class _FakeClient:
        messages = _FakeMessages()

    monkeypatch.setattr(nl_router, "get_client", lambda: _FakeClient())

    def set_response(resp_or_list) -> None:
        state["response"] = resp_or_list

    # Expose call counter for retry-path assertions.
    set_response.calls = state  # type: ignore[attr-defined]
    return set_response


# --- Auth gate ----------------------------------------------------------


def test_nl_requires_auth(client: TestClient) -> None:
    r = client.post("/nl-query", json={"question": "anything"})
    assert r.status_code == 401


def test_nl_503_when_key_missing(
    client: TestClient,
    seeded_data: dict,
    auth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "anthropic_api_key", None, raising=False)
    r = auth_client.post("/nl-query", json={"question": "anything"})
    assert r.status_code == 503


# --- tool routing -------------------------------------------------------


def test_unknown_tool_returns_error(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    """Defensive: if the model somehow picks a tool that isn't in our
    catalogue (e.g. a stale name from cache), we return a structured
    error instead of 500."""
    fake_anthropic(_response([_tool_use_block("ghost_tool", {})]))
    r = auth_client.post("/nl-query", json={"question": "..."})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "error"
    assert "unknown tool" in body["error"]


# --- execute_sql -------------------------------------------------------


def test_execute_sql_safe_select_runs(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    fake_anthropic(
        _response(
            [
                _tool_use_block(
                    "execute_sql",
                    {"sql": "SELECT count(*) AS n FROM employees"},
                )
            ]
        )
    )
    r = auth_client.post("/nl-query", json={"question": "how many employees?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "sql"
    assert "LIMIT" in body["sql"].upper()
    assert body["columns"] == ["n"]
    assert body["rows"][0]["n"] >= 5


def test_execute_sql_dml_rejected_by_guard(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    fake_anthropic(_response([_tool_use_block("execute_sql", {"sql": "DELETE FROM employees"})]))
    r = auth_client.post("/nl-query", json={"question": "delete everyone"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "error"
    assert "unsafe SQL" in body["error"]


# --- text-only response ------------------------------------------------


def test_text_response_when_model_returns_no_tool(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    fake_anthropic(_response([_text_block("I don't have data for that.")]))
    r = auth_client.post("/nl-query", json={"question": "what is the meaning of life?"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "text"
    assert "meaning of life" not in body["text"].lower()
    assert body["text"]  # non-empty


# --- nl_query_log ------------------------------------------------------


def test_query_is_logged(
    auth_client: TestClient,
    seeded_data: dict,
    fake_anthropic,
    db_session,
) -> None:
    fake_anthropic(
        _response(
            [
                _tool_use_block(
                    "execute_sql",
                    {"sql": "SELECT count(*) AS n FROM employees"},
                )
            ]
        )
    )
    auth_client.post(
        "/nl-query",
        json={"question": "count employees please"},
    )
    row = (
        db_session.execute(
            text(
                "SELECT question, tool_picked, sql_emitted, result_rows "
                "FROM nl_query_log "
                "WHERE question = :q "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"q": "count employees please"},
        )
        .mappings()
        .one_or_none()
    )
    assert row is not None
    assert row["tool_picked"] == "execute_sql"
    assert row["sql_emitted"] and "SELECT" in row["sql_emitted"].upper()
    assert row["result_rows"] is not None and row["result_rows"] >= 1


# --- self-correcting retry loop ----------------------------------------


def test_agent_retries_once_after_tool_error(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    """When the first execute_sql attempt errors, the agent must send
    the error back to Claude and try once more. This test simulates
    that two-step flow: first response calls a bogus column (Postgres
    will error), second response calls a valid column (succeeds)."""
    fake_anthropic(
        [
            _response(
                [
                    _tool_use_block(
                        "execute_sql",
                        {"sql": "SELECT nonexistent_column FROM employees"},
                    )
                ]
            ),
            _response(
                [
                    _tool_use_block(
                        "execute_sql",
                        {"sql": "SELECT count(*) AS n FROM employees"},
                    )
                ]
            ),
        ]
    )

    r = auth_client.post("/nl-query", json={"question": "how many employees?"})
    assert r.status_code == 200, r.text
    body = r.json()
    # Second attempt succeeded → SQL response, not error.
    assert body["kind"] == "sql"
    assert body["columns"] == ["n"]
    # Surface the retry count to the caller.
    assert body["meta"]["attempts"] == 2
    # Both Anthropic round trips actually happened.
    assert fake_anthropic.calls["calls"] == 2


def test_agent_gives_up_after_max_attempts(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    """If both attempts fail, return the FINAL error to the caller
    (not the first one — Claude already tried to fix that one)."""
    bad_response = _response(
        [
            _tool_use_block(
                "execute_sql",
                {"sql": "SELECT still_does_not_exist FROM employees"},
            )
        ]
    )
    fake_anthropic([bad_response, bad_response])

    r = auth_client.post("/nl-query", json={"question": "doomed query"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "error"
    assert "tool failed" in body["error"]
    assert body["meta"]["attempts"] == 2
    assert fake_anthropic.calls["calls"] == 2


def test_agent_does_not_retry_on_text_response(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    """A text-only response is a terminal outcome — same prompt would
    produce the same refusal. Don't burn a second Anthropic call."""
    fake_anthropic(_response([_text_block("I don't have data for that.")]))

    r = auth_client.post("/nl-query", json={"question": "what's the meaning of life?"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "text"
    assert body["meta"]["attempts"] == 1
    assert fake_anthropic.calls["calls"] == 1
