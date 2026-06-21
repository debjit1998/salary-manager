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

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

import app.db as app_db  # noqa: E402
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
