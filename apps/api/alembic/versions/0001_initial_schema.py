"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-21

Creates the full data model in one migration: users, lookups
(departments/levels/currencies), employees, comp_bands, salary_changes
(append-only), equity_grants (append-only), nl_query_log, and the
employees_current_salary view. No data is inserted — see scripts/seed.py.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ----------------------------------------------------
    # pgcrypto: gen_random_uuid() for primary keys.
    # pg_trgm:  trigram index on lower(name) for fast 'ILIKE %x%' search.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- users ---------------------------------------------------------
    op.execute(
        """
        CREATE TABLE users (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email         text NOT NULL UNIQUE,
            password_hash text NOT NULL,
            created_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # --- lookups: departments, levels, currencies ----------------------
    op.execute(
        """
        CREATE TABLE departments (
            id   smallserial PRIMARY KEY,
            name text NOT NULL UNIQUE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE levels (
            id   smallserial PRIMARY KEY,
            code text NOT NULL UNIQUE,
            rank smallint NOT NULL UNIQUE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE currencies (
            code         char(3) PRIMARY KEY,
            name         text NOT NULL,
            ratio_to_usd numeric(14, 6) NOT NULL CHECK (ratio_to_usd > 0)
        )
        """
    )

    # --- employees -----------------------------------------------------
    # country, employment_type, status are text + CHECK rather than
    # native ENUMs: ENUMs are painful to evolve (require dedicated
    # migration steps to add a value), and the NL prompt's hints file
    # documents the valid values anyway.
    op.execute(
        """
        CREATE TABLE employees (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_no     text NOT NULL UNIQUE,
            first_name      text NOT NULL,
            last_name       text NOT NULL,
            email           text NOT NULL UNIQUE,
            country         char(2) NOT NULL
                             CHECK (country IN ('US', 'UK', 'IN')),
            department_id   smallint NOT NULL REFERENCES departments(id),
            level_id        smallint NOT NULL REFERENCES levels(id),
            manager_id      uuid REFERENCES employees(id) ON DELETE SET NULL,
            employment_type text NOT NULL
                             CHECK (employment_type IN
                                    ('full_time', 'part_time', 'contractor')),
            hire_date       date NOT NULL,
            status          text NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'terminated')),
            created_at      timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # Filter index for the employee directory page (dept + country + level)
    op.execute(
        """
        CREATE INDEX employees_filter_idx
            ON employees (department_id, country, level_id)
        """
    )
    # Trigram search on full name (lower-cased) for the search box
    op.execute(
        """
        CREATE INDEX employees_name_trgm_idx
            ON employees
            USING gin (lower(first_name || ' ' || last_name) gin_trgm_ops)
        """
    )
    # Reporting tree
    op.execute(
        """
        CREATE INDEX employees_manager_idx
            ON employees (manager_id)
            WHERE manager_id IS NOT NULL
        """
    )

    # --- comp_bands ----------------------------------------------------
    # One row per (level, country). Native currency only; USD is computed
    # at query time by JOINing currencies.
    op.execute(
        """
        CREATE TABLE comp_bands (
            level_id      smallint NOT NULL REFERENCES levels(id),
            country       char(2) NOT NULL
                           CHECK (country IN ('US', 'UK', 'IN')),
            currency_code char(3) NOT NULL REFERENCES currencies(code),
            band_min      numeric(14, 2) NOT NULL,
            band_mid      numeric(14, 2) NOT NULL,
            band_max      numeric(14, 2) NOT NULL,
            PRIMARY KEY (level_id, country),
            CHECK (band_min <= band_mid AND band_mid <= band_max)
        )
        """
    )

    # --- salary_changes (append-only) ----------------------------------
    op.execute(
        """
        CREATE TABLE salary_changes (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id    uuid NOT NULL REFERENCES employees(id)
                             ON DELETE CASCADE,
            effective_date date NOT NULL,
            amount         numeric(14, 2) NOT NULL CHECK (amount > 0),
            currency_code  char(3) NOT NULL REFERENCES currencies(code),
            reason         text NOT NULL
                             CHECK (reason IN
                                    ('hire', 'raise', 'promo', 'adjustment')),
            note           text,
            created_by     uuid REFERENCES users(id),
            created_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # "Latest salary per employee" — drives the current-salary view.
    op.execute(
        """
        CREATE INDEX salary_changes_employee_effective_idx
            ON salary_changes (employee_id, effective_date DESC, id DESC)
        """
    )
    # "Raises in period" — used by the raises_in_period analytics tool.
    op.execute(
        """
        CREATE INDEX salary_changes_effective_idx
            ON salary_changes (effective_date)
        """
    )

    # --- equity_grants (append-only) -----------------------------------
    op.execute(
        """
        CREATE TABLE equity_grants (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            employee_id uuid NOT NULL REFERENCES employees(id)
                          ON DELETE CASCADE,
            grant_date  date NOT NULL,
            shares      int NOT NULL CHECK (shares > 0),
            created_by  uuid REFERENCES users(id),
            created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE INDEX equity_grants_employee_date_idx
            ON equity_grants (employee_id, grant_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX equity_grants_date_idx
            ON equity_grants (grant_date)
        """
    )

    # --- nl_query_log --------------------------------------------------
    # Observability + audit trail for the NL feature.
    op.execute(
        """
        CREATE TABLE nl_query_log (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       uuid REFERENCES users(id),
            question      text NOT NULL,
            tool_picked   text,
            tool_args     jsonb,
            sql_emitted   text,
            result_rows   int,
            latency_ms    int,
            input_tokens  int,
            output_tokens int,
            error         text,
            created_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX nl_query_log_created_at_idx ON nl_query_log (created_at DESC)"
    )

    # --- employees_current_salary view --------------------------------
    # "Current salary" = the latest salary_changes row per employee with
    # effective_date <= today. Tiebreaker is id DESC (deterministic when
    # two rows share an effective_date). amount_usd is computed via JOIN.
    op.execute(
        """
        CREATE VIEW employees_current_salary AS
        SELECT DISTINCT ON (sc.employee_id)
            sc.employee_id,
            sc.amount,
            sc.currency_code,
            sc.effective_date,
            (sc.amount / c.ratio_to_usd)::numeric(14, 2) AS amount_usd
        FROM salary_changes sc
        JOIN currencies c ON c.code = sc.currency_code
        WHERE sc.effective_date <= CURRENT_DATE
        ORDER BY sc.employee_id, sc.effective_date DESC, sc.id DESC
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS employees_current_salary")
    op.execute("DROP TABLE IF EXISTS nl_query_log")
    op.execute("DROP TABLE IF EXISTS equity_grants")
    op.execute("DROP TABLE IF EXISTS salary_changes")
    op.execute("DROP TABLE IF EXISTS comp_bands")
    op.execute("DROP TABLE IF EXISTS employees")
    op.execute("DROP TABLE IF EXISTS currencies")
    op.execute("DROP TABLE IF EXISTS levels")
    op.execute("DROP TABLE IF EXISTS departments")
    op.execute("DROP TABLE IF EXISTS users")
    # Extensions left in place — they may be used by other databases on
    # this cluster, and dropping them would also drop the trigram index
    # we depend on. Cheap to keep.
