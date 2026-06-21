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


def _tool_use_block(name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=args)


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
    and the cached schema block."""
    from app.settings import settings
    from app.src.nl import router as nl_router

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key", raising=False)
    monkeypatch.setattr(nl_router, "_schema_block", "TEST_SCHEMA_BLOCK", raising=False)

    state: dict[str, Any] = {"response": None}

    class _FakeMessages:
        def create(self, **_kw):
            return state["response"]

    class _FakeClient:
        messages = _FakeMessages()

    monkeypatch.setattr(nl_router, "get_client", lambda: _FakeClient())

    def set_response(resp: SimpleNamespace) -> None:
        state["response"] = resp

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


# --- tool-use happy path ------------------------------------------------


def test_tool_use_headcount_by_country(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
    fake_anthropic(
        _response([_tool_use_block("headcount_by", {"dimension": "country"})])
    )
    r = auth_client.post(
        "/nl-query", json={"question": "How many employees by country?"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "tool"
    assert body["tool"] == "headcount_by"
    assert body["args"] == {"dimension": "country"}
    # Result has at least the seeded countries
    dims = {row["dimension"] for row in body["result"]["rows"]}
    assert {"US", "UK", "IN"}.issubset(dims)
    # meta has token counts
    assert body["meta"]["input_tokens"] == 100
    assert body["meta"]["output_tokens"] == 50


def test_tool_use_unknown_tool_returns_error(
    auth_client: TestClient, seeded_data: dict, fake_anthropic
) -> None:
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
    fake_anthropic(
        _response(
            [_tool_use_block("execute_sql", {"sql": "DELETE FROM employees"})]
        )
    )
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
    r = auth_client.post(
        "/nl-query", json={"question": "what is the meaning of life?"}
    )
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
            [_tool_use_block("headcount_by", {"dimension": "department"})]
        )
    )
    auth_client.post(
        "/nl-query",
        json={"question": "headcount by department please"},
    )
    row = (
        db_session.execute(
            text(
                "SELECT question, tool_picked, result_rows "
                "FROM nl_query_log "
                "WHERE question = :q "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"q": "headcount by department please"},
        )
        .mappings()
        .one_or_none()
    )
    assert row is not None
    assert row["tool_picked"] == "headcount_by"
    assert row["result_rows"] is not None and row["result_rows"] >= 1
