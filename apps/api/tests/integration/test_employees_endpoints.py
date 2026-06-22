"""Integration tests for /employees and its sub-resources.

Uses the session-scoped `seeded_data` fixture (defined in conftest)
which inserts 5 fixed employees, 2 departments, 3 levels, 3 currencies,
5 comp bands, plus salary histories and a couple of equity grants.
Per-test mutations roll back via the SAVEPOINT pattern.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi.testclient import TestClient


# --- Auth gate ----------------------------------------------------------


def test_list_requires_auth(client: TestClient) -> None:
    r = client.get("/employees")
    assert r.status_code == 401


def test_detail_requires_auth(client: TestClient, seeded_data: dict) -> None:
    r = client.get(f"/employees/{seeded_data['emp_alice_us_l5_id']}")
    assert r.status_code == 401


# --- List endpoint ------------------------------------------------------


def test_list_returns_seeded_employees(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get("/employees")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["size"] == 25
    assert body["total"] >= 5
    ids = {item["id"] for item in body["items"]}
    assert set(seeded_data["all_employee_ids"]).issubset(ids)


def test_list_pagination(auth_client: TestClient, seeded_data: dict) -> None:
    page1 = auth_client.get("/employees", params={"page": 1, "size": 2}).json()
    page2 = auth_client.get("/employees", params={"page": 2, "size": 2}).json()
    assert page1["size"] == 2
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    # No overlap between pages
    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    assert ids1.isdisjoint(ids2)


def test_list_filter_by_country(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get("/employees", params={"country": "UK", "size": 100})
    body = r.json()
    assert r.status_code == 200
    countries = {i["country"] for i in body["items"]}
    assert countries == {"UK"}
    # Carla is the only UK employee in the seed
    carla_id = seeded_data["emp_carla_uk_l4_id"]
    assert any(i["id"] == carla_id for i in body["items"])


def test_list_filter_by_employment_type(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get(
        "/employees", params={"employment_type": "contractor", "size": 100}
    )
    body = r.json()
    types = {i["employment_type"] for i in body["items"]}
    assert types == {"contractor"}
    assert any(i["id"] == seeded_data["emp_devi_in_l4_id"] for i in body["items"])


def test_list_filter_by_level_and_dept(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get(
        "/employees",
        params={
            "level_id": seeded_data["level_l4_id"],
            "dept_id": seeded_data["dept_engineering_id"],
            "size": 100,
        },
    )
    body = r.json()
    # Bob (US L4 Eng) and Devi (IN L4 Eng) are the L4 engineers
    seed_ids = {seeded_data["emp_bob_us_l4_id"], seeded_data["emp_devi_in_l4_id"]}
    returned = {i["id"] for i in body["items"]}
    assert seed_ids.issubset(returned)
    for item in body["items"]:
        assert item["level"] == "L4"
        assert item["department"] == "Engineering"


def test_list_search_by_name(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get("/employees", params={"q": "carla", "size": 100})
    body = r.json()
    returned = {i["id"] for i in body["items"]}
    assert seeded_data["emp_carla_uk_l4_id"] in returned


def test_list_search_by_email(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get(
        "/employees", params={"q": "bob.brown@test.org", "size": 100}
    )
    body = r.json()
    returned = {i["id"] for i in body["items"]}
    assert seeded_data["emp_bob_us_l4_id"] in returned


def test_list_sort_by_hire_date_desc(auth_client: TestClient) -> None:
    r = auth_client.get("/employees", params={"sort": "-hire_date", "size": 100})
    items = r.json()["items"]
    hire_dates = [i["hire_date"] for i in items]
    assert hire_dates == sorted(hire_dates, reverse=True)


def test_list_sort_invalid_returns_400(auth_client: TestClient) -> None:
    r = auth_client.get("/employees", params={"sort": "password"})
    assert r.status_code == 400


def test_list_includes_band_position(
    auth_client: TestClient, seeded_data: dict
) -> None:
    """Carla is seeded at £90k for a UK L4 band of 100-135k → below band."""
    r = auth_client.get(f"/employees/{seeded_data['emp_carla_uk_l4_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["band_position"] == "below"


# --- Detail endpoint ----------------------------------------------------


def test_detail_returns_history_and_grants(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get(f"/employees/{seeded_data['emp_alice_us_l5_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["employee_no"] == "TEST-00001"
    assert body["first_name"] == "Alice"
    assert body["level"] == "L5"
    # Alice has 2 salary changes (hire + raise) and 1 equity grant
    assert len(body["salary_changes"]) == 2
    assert body["salary_changes"][0]["effective_date"] >= body["salary_changes"][1]["effective_date"]
    assert len(body["equity_grants"]) == 1
    assert body["total_shares"] == 1000
    # Alice has 2 direct reports (Bob, Carla) and no manager
    assert body["manager"] is None
    assert body["direct_reports_count"] == 2


def test_detail_current_salary_is_latest(
    auth_client: TestClient, seeded_data: dict
) -> None:
    body = auth_client.get(
        f"/employees/{seeded_data['emp_alice_us_l5_id']}"
    ).json()
    assert body["current_salary"]["amount"] == "245000.00"
    assert body["current_salary"]["effective_date"] == "2023-04-01"


def test_detail_404_for_unknown(auth_client: TestClient) -> None:
    r = auth_client.get("/employees/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# --- Update endpoint ----------------------------------------------------


def test_patch_updates_employment_type(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_eve_us_l3_id"]
    r = auth_client.patch(f"/employees/{eid}", json={"employment_type": "full_time"})
    assert r.status_code == 200
    assert r.json()["employment_type"] == "full_time"


def test_patch_rejects_self_manager(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_bob_us_l4_id"]
    r = auth_client.patch(f"/employees/{eid}", json={"manager_id": eid})
    assert r.status_code == 400


def test_patch_rejects_unknown_manager(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_bob_us_l4_id"]
    r = auth_client.patch(
        f"/employees/{eid}",
        json={"manager_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 400


def test_patch_404_for_unknown(auth_client: TestClient) -> None:
    r = auth_client.patch(
        "/employees/00000000-0000-0000-0000-000000000000",
        json={"status": "terminated"},
    )
    assert r.status_code == 404


# --- Salary-change endpoint ---------------------------------------------


def test_post_salary_change_appends_to_history(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_bob_us_l4_id"]
    today = date.today().isoformat()
    r = auth_client.post(
        f"/employees/{eid}/salary-changes",
        json={
            "effective_date": today,
            "amount": "180000.00",
            "currency_code": "USD",
            "reason": "raise",
            "note": "merit bump",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount"] == "180000.00"
    assert body["amount_usd"] == "180000.00"
    assert body["reason"] == "raise"

    # The current salary now reflects the new row
    detail = auth_client.get(f"/employees/{eid}").json()
    assert detail["current_salary"]["amount"] == "180000.00"


def test_post_salary_change_rejects_negative_amount(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_bob_us_l4_id"]
    r = auth_client.post(
        f"/employees/{eid}/salary-changes",
        json={
            "effective_date": "2026-01-01",
            "amount": "-1.00",
            "currency_code": "USD",
            "reason": "raise",
        },
    )
    assert r.status_code == 422


def test_post_salary_change_rejects_bad_reason(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_bob_us_l4_id"]
    r = auth_client.post(
        f"/employees/{eid}/salary-changes",
        json={
            "effective_date": "2026-01-01",
            "amount": "100000",
            "currency_code": "USD",
            "reason": "bonus",  # not in enum
        },
    )
    assert r.status_code == 422


def test_post_salary_change_404_for_unknown_employee(
    auth_client: TestClient,
) -> None:
    r = auth_client.post(
        "/employees/00000000-0000-0000-0000-000000000000/salary-changes",
        json={
            "effective_date": "2026-01-01",
            "amount": "100000",
            "currency_code": "USD",
            "reason": "hire",
        },
    )
    assert r.status_code == 404


# --- Equity-grant endpoint ----------------------------------------------


def test_post_equity_grant_appends(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_bob_us_l4_id"]
    r = auth_client.post(
        f"/employees/{eid}/equity-grants",
        json={"grant_date": "2026-06-01", "shares": 250},
    )
    assert r.status_code == 201, r.text
    assert r.json()["shares"] == 250

    detail = auth_client.get(f"/employees/{eid}").json()
    # Bob had 500 from seed + 250 new = 750
    assert detail["total_shares"] == 750


def test_post_equity_grant_rejects_zero_shares(
    auth_client: TestClient, seeded_data: dict
) -> None:
    eid = seeded_data["emp_bob_us_l4_id"]
    r = auth_client.post(
        f"/employees/{eid}/equity-grants",
        json={"grant_date": "2026-06-01", "shares": 0},
    )
    assert r.status_code == 422


# --- CSV export ---------------------------------------------------------

_EXPORT_HEADER = [
    "employee_no",
    "first_name",
    "last_name",
    "email",
    "country",
    "department",
    "level",
    "employment_type",
    "status",
    "hire_date",
    "current_salary_amount",
    "current_salary_currency",
    "current_salary_usd",
    "salary_effective_date",
    "band_position",
]


def _parse_csv(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body)))


def test_export_requires_auth(client: TestClient) -> None:
    r = client.get("/employees/export.csv")
    assert r.status_code == 401


def test_export_returns_streaming_csv(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get("/employees/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    # Filename includes today's date — exact format `employees-YYYY-MM-DD.csv`
    assert f"employees-{date.today().isoformat()}.csv" in cd

    rows = _parse_csv(r.text)
    assert rows[0] == _EXPORT_HEADER
    # Body rows: at least the 5 seeded employees
    assert len(rows) - 1 >= len(seeded_data["all_employee_ids"])


def test_export_respects_country_filter(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get("/employees/export.csv", params={"country": "UK"})
    assert r.status_code == 200
    reader = csv.DictReader(io.StringIO(r.text))
    body = list(reader)
    # Every exported row is UK, and Carla (the only seeded UK employee) is in it
    assert body, "expected at least one UK row"
    assert {row["country"] for row in body} == {"UK"}
    assert any(row["first_name"] == "Carla" for row in body)


def test_export_respects_multi_value_filter(
    auth_client: TestClient, seeded_data: dict
) -> None:
    # axios on the FE sends repeated keys; httpx accepts a list for the same.
    r = auth_client.get(
        "/employees/export.csv", params=[("country", "UK"), ("country", "IN")]
    )
    assert r.status_code == 200
    reader = csv.DictReader(io.StringIO(r.text))
    countries = {row["country"] for row in reader}
    assert countries.issubset({"UK", "IN"})
    assert "UK" in countries and "IN" in countries


def test_export_respects_sort(auth_client: TestClient) -> None:
    r = auth_client.get(
        "/employees/export.csv", params={"sort": "-hire_date"}
    )
    assert r.status_code == 200
    reader = csv.DictReader(io.StringIO(r.text))
    hire_dates = [row["hire_date"] for row in reader]
    assert hire_dates == sorted(hire_dates, reverse=True)


def test_export_invalid_sort_returns_400(auth_client: TestClient) -> None:
    r = auth_client.get(
        "/employees/export.csv", params={"sort": "not_a_real_column"}
    )
    assert r.status_code == 400


def test_export_empty_when_filter_matches_nothing(
    auth_client: TestClient,
) -> None:
    # No seed employee has country "ZZ" — should be header-only output
    r = auth_client.get("/employees/export.csv", params={"country": "ZZ"})
    assert r.status_code == 200
    rows = _parse_csv(r.text)
    assert rows == [_EXPORT_HEADER]


def test_export_search_narrows_rows(
    auth_client: TestClient, seeded_data: dict
) -> None:
    r = auth_client.get("/employees/export.csv", params={"q": "carla"})
    assert r.status_code == 200
    reader = csv.DictReader(io.StringIO(r.text))
    body = list(reader)
    assert body, "expected at least one matching row"
    assert all("carla" in row["first_name"].lower() for row in body)


def test_export_route_is_not_shadowed_by_detail_route(
    auth_client: TestClient,
) -> None:
    """Regression guard. /export.csv MUST be declared before /{employee_id}
    — otherwise FastAPI parses it as employee_id='export.csv' and returns 404.
    """
    r = auth_client.get("/employees/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
