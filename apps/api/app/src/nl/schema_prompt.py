"""Build the NL-query system-prompt schema block.

Two sources merged at app boot:
  1. `information_schema` introspection of the live DB — always current,
     can't drift from the schema.
  2. `schema_hints.yaml` — hand-maintained semantic notes that
     introspection can't infer (append-only invariants, prefer-this-view
     guidance, enum values, etc.).

The result is cached in memory; auto-invalidates on app restart (which
is every deploy). A YAML-vs-schema validator runs at startup and
refuses to boot if the hints reference a table/column that no longer
exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

HINTS_PATH = Path(__file__).parent / "schema_hints.yaml"


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool
    fk: tuple[str, str] | None = None  # (table, column)


@dataclass
class Table:
    name: str
    kind: str  # "table" or "view"
    columns: list[Column]


_INTROSPECT_SQL = """
SELECT
    c.table_name,
    t.table_type,
    c.column_name,
    c.data_type,
    c.is_nullable
FROM information_schema.columns c
JOIN information_schema.tables t
  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
WHERE c.table_schema = 'public'
ORDER BY c.table_name, c.ordinal_position;
"""

_FK_SQL = """
SELECT
    kcu.table_name,
    kcu.column_name,
    ccu.table_name  AS foreign_table,
    ccu.column_name AS foreign_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public';
"""


def introspect(engine: Engine) -> dict[str, Table]:
    with engine.connect() as conn:
        col_rows = conn.execute(text(_INTROSPECT_SQL)).all()
        fk_rows = conn.execute(text(_FK_SQL)).all()

    # (table, column) -> (foreign_table, foreign_column)
    fks: dict[tuple[str, str], tuple[str, str]] = {
        (r.table_name, r.column_name): (r.foreign_table, r.foreign_column) for r in fk_rows
    }

    tables: dict[str, Table] = {}
    for r in col_rows:
        if r.table_name == "alembic_version":
            continue  # internal bookkeeping
        kind = "view" if r.table_type == "VIEW" else "table"
        t = tables.setdefault(r.table_name, Table(r.table_name, kind, []))
        t.columns.append(
            Column(
                name=r.column_name,
                data_type=r.data_type,
                nullable=(r.is_nullable == "YES"),
                fk=fks.get((r.table_name, r.column_name)),
            )
        )
    return tables


def load_hints() -> dict[str, Any]:
    return yaml.safe_load(HINTS_PATH.read_text()) or {}


# Tables whose entire content is small and stable, and where the rows
# act as enum values that the LLM needs at tool-call time. We include
# them inline in the schema prompt so Claude can resolve
# "Engineering" → department_id=1 without writing a lookup query.
REFERENCE_TABLES = ("departments", "levels", "currencies")


def fetch_reference_data(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    """Pull the contents of small enum-like tables at app boot. Used to
    inline name→id mappings into the system prompt so the LLM can
    filter by department / level without a lookup roundtrip."""
    queries = {
        "departments": "SELECT id, name FROM departments ORDER BY id",
        "levels": "SELECT id, code, rank FROM levels ORDER BY rank",
        "currencies": ("SELECT code, name, ratio_to_usd FROM currencies ORDER BY code"),
    }
    out: dict[str, list[dict[str, Any]]] = {}
    with engine.connect() as conn:
        for name, sql in queries.items():
            try:
                rows = conn.execute(text(sql)).mappings().all()
                out[name] = [dict(r) for r in rows]
            except Exception:  # noqa: BLE001
                # Best-effort — if a table doesn't exist yet (fresh DB),
                # just skip its inline data.
                out[name] = []
    return out


class SchemaHintError(RuntimeError):
    """Raised at startup if schema_hints.yaml references a missing
    table/column. Keeps the hints from rotting silently."""


def validate_hints(tables: dict[str, Table], hints: dict[str, Any]) -> None:
    for tname, thints in hints.items():
        table = tables.get(tname)
        if table is None:
            raise SchemaHintError(f"schema_hints.yaml references unknown table/view: {tname!r}")
        column_names = {c.name for c in table.columns}
        for cname in (thints or {}).get("columns", {}):
            if cname not in column_names:
                raise SchemaHintError(
                    f"schema_hints.yaml references unknown column: " f"{tname}.{cname!r}"
                )


def _format_reference_rows(name: str, rows: list[dict[str, Any]]) -> list[str]:
    """One-line summaries of reference-table contents (enum-like data)."""
    if not rows:
        return []
    if name == "departments":
        return [
            "  REFERENCE DATA (id → name):"
            + "".join(f"\n    {r['id']} = {r['name']}" for r in rows)
        ]
    if name == "levels":
        return [
            "  REFERENCE DATA (id → code, rank):"
            + "".join(f"\n    {r['id']} = {r['code']} (rank {r['rank']})" for r in rows)
        ]
    if name == "currencies":
        return [
            "  REFERENCE DATA (code, ratio_to_usd):"
            + "".join(f"\n    {r['code']} → ratio {r['ratio_to_usd']}" for r in rows)
        ]
    return []


def render(
    tables: dict[str, Table],
    hints: dict[str, Any],
    reference_data: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    reference_data = reference_data or {}
    out: list[str] = []
    for name in sorted(tables):
        table = tables[name]
        thints = hints.get(name, {}) or {}
        kind = (thints.get("kind") or table.kind).upper()
        out.append(f"\n{kind} {name}")
        col_hints = thints.get("columns", {}) or {}
        for col in table.columns:
            line = f"  {col.name}: {col.data_type}"
            if col.fk:
                line += f"  → {col.fk[0]}.{col.fk[1]}"
            ch = col_hints.get(col.name)
            if isinstance(ch, str):
                line += f"  -- {ch}"
            elif isinstance(ch, dict):
                desc = ch.get("description", "")
                vals = ch.get("values")
                bits = []
                if desc:
                    bits.append(desc)
                if vals:
                    bits.append(f"values: {', '.join(map(str, vals))}")
                if bits:
                    line += "  -- " + ". ".join(bits)
            out.append(line)
        for note in thints.get("notes", []) or []:
            out.append(f"  NOTE: {note}")
        # Inline reference-table contents so the LLM can resolve names
        # to ids without writing a lookup query.
        if name in reference_data:
            out.extend(_format_reference_rows(name, reference_data[name]))
    return "\n".join(out).strip()


def build_schema_prompt(engine: Engine) -> str:
    """Top-level: introspect, validate hints, render. Call once at app boot."""
    tables = introspect(engine)
    hints = load_hints()
    validate_hints(tables, hints)
    reference_data = fetch_reference_data(engine)
    return render(tables, hints, reference_data)
