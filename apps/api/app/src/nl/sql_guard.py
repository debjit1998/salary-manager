"""SQL safety guard for the NL endpoint's `execute_sql` fallback tool.

Defence in depth — three layers protect the database:

  1. **This guard (sqlglot AST validation)** rejects:
       - multi-statement input
       - anything whose root is not a SELECT
       - any descendant DML/DDL node (Insert, Update, Delete, Create,
         Drop, Alter, Truncate, Merge, Grant, Revoke, Commit, Rollback)
       - explicit forbidden functions (e.g. pg_sleep, pg_read_file)
     and rewrites the SELECT to add `LIMIT 1000` if absent.

  2. **A read-only Postgres role** (`nl_readonly`, created by migration
     0002) — the executor switches to this role for the duration of
     the query. Even if a DELETE somehow got through this guard, the
     role would refuse it.

  3. **statement_timeout=10s** on the executing transaction, so
     pathological queries can't lock up the server.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

MAX_ROWS = 1000

# DML/DDL nodes that must never appear in the parsed tree, even as a
# descendant (e.g. inside a CTE or a subquery).
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Merge,
    exp.Commit,
    exp.Rollback,
    # Postgres extension verbs that sqlglot doesn't lump into the above
    exp.Command,
)

# Block specific dangerous Postgres functions even if they appear inside
# a SELECT.
FORBIDDEN_FUNCTIONS: set[str] = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_export",
    "lo_import",
    "copy",
    "dblink",
    "dblink_exec",
}


class SqlGuardError(ValueError):
    """Raised when a candidate SQL string fails validation."""


def validate_select(sql: str) -> str:
    """Validate and normalise a candidate SELECT.

    Returns the (possibly LIMIT-augmented) safe SQL string. Raises
    SqlGuardError if anything is wrong.
    """
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise SqlGuardError("empty SQL")

    try:
        statements = sqlglot.parse(stripped, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise SqlGuardError(f"SQL did not parse: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlGuardError(
            f"only single statements allowed, got {len(statements)}"
        )

    root = statements[0]
    if not isinstance(root, exp.Select):
        raise SqlGuardError(
            f"only SELECT allowed; got {type(root).__name__}"
        )

    # Walk the entire tree (including subqueries / CTEs) and reject any
    # forbidden node type.
    for node in root.walk():
        n = node[0] if isinstance(node, tuple) else node
        if isinstance(n, FORBIDDEN_NODES):
            raise SqlGuardError(
                f"forbidden statement type: {type(n).__name__}"
            )
        if isinstance(n, exp.Func):
            fname = (n.name or "").lower()
            if fname in FORBIDDEN_FUNCTIONS:
                raise SqlGuardError(f"forbidden function: {fname}")
        if isinstance(n, exp.Anonymous):
            # User-defined / unknown function call by name (sqlglot
            # parses these as `Anonymous`). Check the name too.
            fname = (n.this or "").lower() if isinstance(n.this, str) else ""
            if fname in FORBIDDEN_FUNCTIONS:
                raise SqlGuardError(f"forbidden function: {fname}")

    # Force a LIMIT — protects against accidentally streaming millions
    # of rows even though the read-only role would technically allow it.
    if root.args.get("limit") is None:
        root = root.limit(MAX_ROWS)
    else:
        # Cap any user-supplied LIMIT at MAX_ROWS.
        current = root.args["limit"]
        try:
            n = int(current.expression.this)
            if n > MAX_ROWS:
                root = root.limit(MAX_ROWS)
        except (AttributeError, TypeError, ValueError):
            root = root.limit(MAX_ROWS)

    return root.sql(dialect="postgres")
