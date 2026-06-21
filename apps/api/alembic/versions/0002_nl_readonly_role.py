"""nl_readonly role + grants for the NL SQL fallback

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21

The NL query feature's SQL fallback (when no analytics tool fits) runs
the LLM-emitted SELECT against this role. The role:
  - cannot log in (NOLOGIN; the app connects as the regular DB user
    and uses SET SESSION AUTHORIZATION to switch)
  - has SELECT on every public-schema table and the current-salary view
  - has DEFAULT PRIVILEGES so any future tables are also readable
  - has no INSERT/UPDATE/DELETE/DDL grants anywhere

Even if the LLM emits a DELETE, the role refuses to execute it. The
sqlglot guard catches most of that earlier; this is defense in depth.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE = "nl_readonly"


def upgrade() -> None:
    # CREATE ROLE is global to the Postgres cluster (not per-database),
    # so we guard against it already existing — useful for re-running
    # migrations against a cluster that already has the role.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} NOLOGIN;
            END IF;
        END $$;
        """
    )

    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE}")

    # Make new tables / views readable without re-granting.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT ON TABLES TO {ROLE}"
    )


def downgrade() -> None:
    # Revoke in reverse, then drop the role. The DROP fails if anything
    # still depends on the role, so we revoke explicitly first.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT ON TABLES FROM {ROLE}"
    )
    op.execute(f"REVOKE SELECT ON ALL SEQUENCES IN SCHEMA public FROM {ROLE}")
    op.execute(f"REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM {ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {ROLE}")
