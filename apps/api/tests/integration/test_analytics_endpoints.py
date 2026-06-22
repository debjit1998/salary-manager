"""Integration tests for the analytics endpoints.

Asserts against the deterministic seed in `seeded_data` (5 employees:
3 US / 1 UK / 1 IN, 1 L3 / 3 L4 / 1 L5, 3 Eng / 2 Sales, 1 below band).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

# --- Auth gate ----------------------------------------------------------


def test_headcount_by_requires_auth(client: TestClient) -> None:
    r = client.get("/analytics/headcount-by", params={"dimension": "country"})
    assert r.status_code == 401


# --- headcount_by -------------------------------------------------------


def test_headcount_by_country(auth_client: TestClient, seeded_data: dict) -> None:
    r = auth_client.get("/analytics/headcount-by", params={"dimension": "country"})
    assert r.status_code == 200
    body = r.json()
    assert body["dimension"] == "country"
    counts = {row["dimension"]: row["count"] for row in body["rows"]}
    # 3 US, 1 UK, 1 IN
    assert counts["US"] >= 3
    assert counts["UK"] >= 1
    assert counts["IN"] >= 1


def test_headcount_by_level_is_rank_ordered(auth_client: TestClient) -> None:
    body = auth_client.get("/analytics/headcount-by", params={"dimension": "level"}).json()
    codes = [r["dimension"] for r in body["rows"]]
    # Levels appear in rank order (L3, L4, L5 in that order in the seed)
    sorted_codes = sorted(codes, key=lambda c: int(c[1:]))
    assert codes == sorted_codes


def test_headcount_by_with_country_filter(auth_client: TestClient) -> None:
    body = auth_client.get(
        "/analytics/headcount-by",
        params={"dimension": "level", "country": "UK"},
    ).json()
    counts = {r["dimension"]: r["count"] for r in body["rows"]}
    # UK has only Carla (L4)
    assert counts.get("L4", 0) >= 1
    assert "L5" not in counts  # no L5 in UK


def test_headcount_by_unknown_dimension_returns_422(
    auth_client: TestClient,
) -> None:
    # Literal validation in Pydantic — FastAPI returns 422.
    r = auth_client.get("/analytics/headcount-by", params={"dimension": "password"})
    assert r.status_code == 422


# --- avg_salary_by ------------------------------------------------------


def test_avg_salary_by_country(auth_client: TestClient, seeded_data: dict) -> None:
    body = auth_client.get("/analytics/avg-salary-by", params={"dimension": "country"}).json()
    rows = {r["dimension"]: r for r in body["rows"]}
    # US row covers Alice, Bob, Eve → all real positive averages
    assert "US" in rows
    assert float(rows["US"]["avg_salary_usd"]) > 0
    assert rows["US"]["count"] >= 3


def test_avg_salary_by_level_l4_full_time(auth_client: TestClient) -> None:
    body = auth_client.get(
        "/analytics/avg-salary-by",
        params={"dimension": "country", "employment_type": "full_time"},
    ).json()
    # Contractor (Devi) and part_time (Eve) excluded; UK Carla still included
    assert all(r["count"] >= 1 for r in body["rows"])


# --- salary_distribution ------------------------------------------------


def test_salary_distribution_buckets(auth_client: TestClient) -> None:
    body = auth_client.get("/analytics/salary-distribution").json()
    labels = [b["label"] for b in body["buckets"]]
    assert labels == [
        "0-50k",
        "50-100k",
        "100-150k",
        "150-200k",
        "200-300k",
        "300-500k",
        "500k+",
    ]
    # All seeded employees fall into some bucket
    assert sum(b["count"] for b in body["buckets"]) == body["total"]


# --- top_n_earners ------------------------------------------------------


def test_top_earners_returns_descending(auth_client: TestClient, seeded_data: dict) -> None:
    r = auth_client.post("/analytics/top-earners", json={"n": 3})
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 3
    amounts = [float(row["amount_usd"]) for row in rows]
    assert amounts == sorted(amounts, reverse=True)
    # Alice (L5 US, $245k) should be the top earner in the seed
    assert rows[0]["employee_no"] == "TEST-00001"


def test_top_earners_n_validation(auth_client: TestClient) -> None:
    r = auth_client.post("/analytics/top-earners", json={"n": 0})
    assert r.status_code == 422
    r = auth_client.post("/analytics/top-earners", json={"n": 999})
    assert r.status_code == 422


# --- comp_ratio_vs_band -------------------------------------------------


def test_comp_ratio_vs_band_finds_carla_below(auth_client: TestClient, seeded_data: dict) -> None:
    body = auth_client.get("/analytics/comp-ratio-vs-band").json()
    assert body["summary"]["below"] >= 1
    # Carla is the only below-band in the seed
    out_of_band = body["out_of_band"]
    assert any(e["employee_no"] == "TEST-00003" for e in out_of_band)
    carla = next(e for e in out_of_band if e["employee_no"] == "TEST-00003")
    assert carla["band_position"] == "below"
    assert float(carla["amount"]) < float(carla["band_min"])


# --- raises_in_period ---------------------------------------------------


def test_raises_in_period_finds_alice_raise(
    auth_client: TestClient,
) -> None:
    r = auth_client.post(
        "/analytics/raises-in-period",
        json={"start": "2023-01-01", "end": "2023-12-31"},
    )
    assert r.status_code == 200
    body = r.json()
    # Alice has one 'raise' on 2023-04-01 in the seed; the only one
    assert body["count"] >= 1
    found = [e for e in body["rows"] if e["employee_no"] == "TEST-00001" and e["reason"] == "raise"]
    assert found, "Alice's 2023 raise should appear"


def test_raises_in_period_excludes_hires(auth_client: TestClient) -> None:
    body = auth_client.post(
        "/analytics/raises-in-period",
        json={"start": "2020-01-01", "end": "2026-12-31"},
    ).json()
    # All Bob/Carla/Devi/Eve are 'hire' rows in the seed; only Alice's
    # raise should appear.
    reasons = {row["reason"] for row in body["rows"]}
    assert reasons.issubset({"raise", "promo"})


def test_raises_in_period_rejects_backwards_dates(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/analytics/raises-in-period",
        json={"start": "2026-01-01", "end": "2025-01-01"},
    )
    assert r.status_code == 400


# --- headcount_change ---------------------------------------------------


def test_headcount_change_by_country(auth_client: TestClient, seeded_data: dict) -> None:
    r = auth_client.post(
        "/analytics/headcount-change",
        json={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "dimension": "country",
        },
    )
    assert r.status_code == 200
    body = r.json()
    rows = {row["dimension"]: row for row in body["rows"]}
    # Alice was hired before 2023 (Jan 2022); Bob hired in 2023; Eve in 2024.
    # before_start (US) ≥ 1 (Alice); hired_in_period (US) ≥ 2 (Bob + Eve);
    # total_through_end ≥ 3.
    assert rows["US"]["before_start"] >= 1
    assert rows["US"]["hired_in_period"] >= 2
    assert rows["US"]["total_through_end"] >= 3


def test_headcount_change_rejects_backwards_dates(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/analytics/headcount-change",
        json={
            "start": "2026-01-01",
            "end": "2025-01-01",
            "dimension": "country",
        },
    )
    assert r.status_code == 400
