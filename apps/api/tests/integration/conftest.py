"""Integration-test fixtures.

These tests run against a real Postgres because we depend on
Postgres-specific features (pgcrypto, pg_trgm, RETURNING, distinct on,
etc.). To stay isolated from the dev database that holds the seeded
10k employees, integration tests use a dedicated database
`salary_manager_test` on the same Postgres instance — created once
per pytest session, schema dropped + re-migrated before tests run.

Within a session, each test runs inside a transaction + SAVEPOINT that
gets rolled back on teardown, so tests can freely insert without
seeing each other's data.

To run:

    docker compose -f docker-compose.dev.yml up -d   # needs Postgres on :5432
    pytest tests/integration
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Project root is apps/api/ — two levels up from this file.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Resolve the test DB URL BEFORE importing any app module. The default
# matches the dev compose setup (port 5432, user/db = salary). Override
# via env if your local setup differs.
TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "salary_manager_test")
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+psycopg://salary:salary@localhost:5432/{TEST_DB_NAME}",
)
ADMIN_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# ---- App imports (must come AFTER setting DATABASE_URL) ------------------

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

import app.db as app_db  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.main import app  # noqa: E402
from app.src.common.auth import hash_password  # noqa: E402

# If the top-level tests/conftest.py was imported first, app.db.engine
# was created against the unreachable default URL. Rebind it now to the
# real test DB so fixtures and the dependency-overridden client use it.
if str(app_db.engine.url) != TEST_DATABASE_URL:
    app_db.engine.dispose()
    app_db.engine = create_engine(TEST_DATABASE_URL, future=True, pool_pre_ping=True)


# ---- One-shot setup: create the test DB, reset schema, migrate -----------


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db() -> Iterator[None]:
    """Create `salary_manager_test` if it doesn't exist, drop+recreate
    `public` schema, apply Alembic migrations. Runs once per pytest
    session, before any test."""
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        existing = c.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": TEST_DB_NAME},
        ).fetchone()
        if not existing:
            c.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin.dispose()

    test_admin = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with test_admin.connect() as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
        c.execute(text("GRANT ALL ON SCHEMA public TO salary"))
    test_admin.dispose()

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")

    yield


# ---- Per-test fixtures ---------------------------------------------------


@pytest.fixture()
def db_connection() -> Iterator[Connection]:
    """One Connection per test wrapped in a transaction that is rolled
    back on teardown. App-code commits don't end this transaction because
    the session below uses `join_transaction_mode="create_savepoint"`.
    """
    connection = app_db.engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture()
def db_session(db_connection: Connection) -> Iterator[Session]:
    """Session bound to the test's outer transaction.

    `join_transaction_mode="create_savepoint"` is the SQLAlchemy 2.0
    idiom for test isolation: every `session.commit()` from app code
    creates and releases a SAVEPOINT inside the outer transaction
    instead of ending it. The outer transaction rollback at teardown
    undoes everything the test wrote.
    """
    Maker = sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    with Maker() as s:
        yield s


TEST_HR_EMAIL = "test-hr@acme.org"
TEST_HR_PASSWORD = "test-password-xyz"


@pytest.fixture()
def test_user(db_session: Session) -> dict[str, str]:
    """Insert a fresh HR user for the test; rolled back on teardown."""
    user_id = db_session.execute(
        text(
            """
            INSERT INTO users (email, password_hash)
            VALUES (:email, :password_hash)
            RETURNING id
            """
        ),
        {"email": TEST_HR_EMAIL, "password_hash": hash_password(TEST_HR_PASSWORD)},
    ).scalar_one()
    db_session.commit()
    return {"id": str(user_id), "email": TEST_HR_EMAIL, "password": TEST_HR_PASSWORD}


# --- Session-scoped seed for employee/analytics integration tests ---------
#
# Inserts a deterministic minimal dataset: a session HR user, 2 departments,
# 3 levels, 3 currencies, comp bands, and 5 employees with controlled
# salary histories and a couple of equity grants. The data is COMMITTED at
# session level (i.e. outside the per-test outer transaction), so it
# persists across tests; per-test mutations stay isolated inside the
# SAVEPOINT.
#
# Returns a dict of well-known IDs so tests can assert on specific rows.


SEED_HR_EMAIL = "session-hr@acme.org"
SEED_HR_PASSWORD = "session-password-xyz"


@pytest.fixture(scope="session")
def seeded_data() -> dict[str, object]:
    from sqlalchemy import create_engine as _ce  # local alias

    raw = _ce(TEST_DATABASE_URL, future=True)
    out: dict[str, object] = {}
    with raw.begin() as c:
        # HR user
        out["hr_user_id"] = str(
            c.execute(
                text(
                    "INSERT INTO users (email, password_hash) "
                    "VALUES (:e, :p) "
                    "ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email "
                    "RETURNING id"
                ),
                {"e": SEED_HR_EMAIL, "p": hash_password(SEED_HR_PASSWORD)},
            ).scalar_one()
        )

        # Departments
        for name in ("Engineering", "Sales"):
            c.execute(
                text("INSERT INTO departments (name) VALUES (:n) ON CONFLICT DO NOTHING"),
                {"n": name},
            )
        dept_rows = c.execute(text("SELECT id, name FROM departments")).all()
        depts = {name: id_ for id_, name in dept_rows}
        out["dept_engineering_id"] = depts["Engineering"]
        out["dept_sales_id"] = depts["Sales"]

        # Levels
        for code, rank in (("L3", 3), ("L4", 4), ("L5", 5)):
            c.execute(
                text("INSERT INTO levels (code, rank) VALUES (:c, :r) " "ON CONFLICT DO NOTHING"),
                {"c": code, "r": rank},
            )
        level_rows = c.execute(text("SELECT id, code FROM levels")).all()
        levels = {code: id_ for id_, code in level_rows}
        out["level_l3_id"] = levels["L3"]
        out["level_l4_id"] = levels["L4"]
        out["level_l5_id"] = levels["L5"]

        # Currencies
        for code, name, ratio in (
            ("USD", "US Dollar", "1.000000"),
            ("GBP", "Pound Sterling", "0.755800"),
            ("INR", "Indian Rupee", "94.460000"),
        ):
            c.execute(
                text(
                    "INSERT INTO currencies (code, name, ratio_to_usd) "
                    "VALUES (:c, :n, :r) ON CONFLICT (code) DO NOTHING"
                ),
                {"c": code, "n": name, "r": ratio},
            )

        # Comp bands — only the (level, country) combos used below
        bands = [
            (levels["L3"], "US", "USD", 110000, 130000, 150000),
            (levels["L4"], "US", "USD", 150000, 175000, 200000),
            (levels["L5"], "US", "USD", 200000, 240000, 280000),
            (levels["L4"], "UK", "GBP", 100000, 117500, 135000),
            (levels["L4"], "IN", "INR", 2500000, 3200000, 4000000),
        ]
        for lid, country, cur, mn, md, mx in bands:
            c.execute(
                text(
                    "INSERT INTO comp_bands "
                    "  (level_id, country, currency_code, band_min, band_mid, band_max) "
                    "VALUES (:l, :country, :cur, :mn, :md, :mx) "
                    "ON CONFLICT (level_id, country) DO NOTHING"
                ),
                {"l": lid, "country": country, "cur": cur, "mn": mn, "md": md, "mx": mx},
            )

        # Employees — 5 fixed identities with controlled salary histories.
        # Ordering is intentional: emp[0] is L5 with no manager (top of chain).
        employees = [
            {
                "no": "TEST-00001",
                "first": "Alice",
                "last": "Anderson",
                "email": "alice.anderson@test.org",
                "country": "US",
                "dept_id": depts["Engineering"],
                "level_id": levels["L5"],
                "employment_type": "full_time",
                "hire_date": "2022-01-15",
                "salary": [
                    ("2022-01-15", 230000, "USD", "hire"),
                    ("2023-04-01", 245000, "USD", "raise"),
                ],
                "grants": [("2022-02-01", 1000)],
            },
            {
                "no": "TEST-00002",
                "first": "Bob",
                "last": "Brown",
                "email": "bob.brown@test.org",
                "country": "US",
                "dept_id": depts["Engineering"],
                "level_id": levels["L4"],
                "employment_type": "full_time",
                "hire_date": "2023-03-10",
                "salary": [("2023-03-10", 165000, "USD", "hire")],
                "grants": [("2023-04-01", 500)],
            },
            {
                "no": "TEST-00003",
                "first": "Carla",
                "last": "Clarke",
                "email": "carla.clarke@test.org",
                "country": "UK",
                "dept_id": depts["Sales"],
                "level_id": levels["L4"],
                "employment_type": "full_time",
                "hire_date": "2023-06-01",
                "salary": [("2023-06-01", 90000, "GBP", "hire")],  # BELOW band
                "grants": [],
            },
            {
                "no": "TEST-00004",
                "first": "Devi",
                "last": "Desai",
                "email": "devi.desai@test.org",
                "country": "IN",
                "dept_id": depts["Engineering"],
                "level_id": levels["L4"],
                "employment_type": "contractor",
                "hire_date": "2024-01-08",
                "salary": [("2024-01-08", 3200000, "INR", "hire")],
                "grants": [],
            },
            {
                "no": "TEST-00005",
                "first": "Eve",
                "last": "Evans",
                "email": "eve.evans@test.org",
                "country": "US",
                "dept_id": depts["Sales"],
                "level_id": levels["L3"],
                "employment_type": "part_time",
                "hire_date": "2024-09-20",
                "salary": [("2024-09-20", 125000, "USD", "hire")],
                "grants": [],
            },
        ]
        ids: list[str] = []
        for e in employees:
            eid = str(
                c.execute(
                    text(
                        "INSERT INTO employees "
                        "  (employee_no, first_name, last_name, email, country, "
                        "   department_id, level_id, employment_type, hire_date, status) "
                        "VALUES (:no, :first, :last, :email, :country, :dept_id, "
                        "        :level_id, :employment_type, :hire_date, 'active') "
                        "RETURNING id"
                    ),
                    e,
                ).scalar_one()
            )
            ids.append(eid)
            for d, amt, cur, reason in e["salary"]:
                c.execute(
                    text(
                        "INSERT INTO salary_changes "
                        "  (employee_id, effective_date, amount, currency_code, "
                        "   reason, created_by) "
                        "VALUES (:e, :d, :a, :cur, :r, :u)"
                    ),
                    {
                        "e": eid,
                        "d": d,
                        "a": amt,
                        "cur": cur,
                        "r": reason,
                        "u": out["hr_user_id"],
                    },
                )
            for d, shares in e["grants"]:
                c.execute(
                    text(
                        "INSERT INTO equity_grants "
                        "  (employee_id, grant_date, shares, created_by) "
                        "VALUES (:e, :d, :s, :u)"
                    ),
                    {"e": eid, "d": d, "s": shares, "u": out["hr_user_id"]},
                )

        # Alice (emp[0], L5) becomes manager for Bob and Carla
        c.execute(
            text("UPDATE employees SET manager_id = :m WHERE id IN (:b, :ca)"),
            {"m": ids[0], "b": ids[1], "ca": ids[2]},
        )

    out["emp_alice_us_l5_id"] = ids[0]
    out["emp_bob_us_l4_id"] = ids[1]
    out["emp_carla_uk_l4_id"] = ids[2]
    out["emp_devi_in_l4_id"] = ids[3]
    out["emp_eve_us_l3_id"] = ids[4]
    out["all_employee_ids"] = ids
    out["hr_email"] = SEED_HR_EMAIL
    out["hr_password"] = SEED_HR_PASSWORD

    yield out


@pytest.fixture()
def auth_client(client: TestClient, seeded_data: dict) -> TestClient:
    """A TestClient that's already logged in as the session HR user."""
    r = client.post(
        "/auth/login",
        json={"email": seeded_data["hr_email"], "password": seeded_data["hr_password"]},
    )
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """FastAPI TestClient with `get_session` overridden to yield the
    transactionally-isolated session from this test.
    """
    from app.db import get_session

    def override_get_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
