"""SQL + pure helpers for the employee endpoints.

Keeping the SQL out of router.py makes both files easier to read and
gives the pure helpers (sort parser, filter builder) something to be
unit-tested against without a DB.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# --- Pure helpers (unit-testable) ----------------------------------------

# Whitelist of user-facing sort keys → SQL columns. Anything not in this
# map is rejected at parse time — no risk of SQL injection via `sort`
# even though we string-interpolate the column name into the query.
ALLOWED_SORTS: dict[str, str] = {
    "employee_no": "e.employee_no",
    "first_name": "e.first_name",
    "last_name": "e.last_name",
    "email": "e.email",
    "hire_date": "e.hire_date",
    "level": "l.rank",
    "current_salary_usd": "ecs.amount_usd",
}

# Salary-band filter buckets — USD-equivalent ranges. The keys are
# what the FE sends and what we match in SQL via a CASE expression;
# the FE renders human-readable labels next to each key.
ALLOWED_SALARY_BANDS: tuple[str, ...] = (
    "0-10000",
    "10000-50000",
    "50000-100000",
    "100000-150000",
    "150000-200000",
    "200000-300000",
    "300000+",
)


def parse_sort(sort: str | None) -> tuple[str, str]:
    """Parse 'hire_date' or '-hire_date' into (sql_column, direction).

    Returns ('e.employee_no', 'ASC') for empty / None input. Raises
    ValueError on unknown keys so the router can turn it into a 400.
    """
    if not sort:
        return ALLOWED_SORTS["employee_no"], "ASC"
    descending = sort.startswith("-")
    key = sort[1:] if descending else sort
    column = ALLOWED_SORTS.get(key)
    if column is None:
        raise ValueError(f"unsupported sort key: {key!r}. valid keys: {sorted(ALLOWED_SORTS)}")
    return column, "DESC" if descending else "ASC"


def build_filters(
    *,
    q: str | None = None,
    dept_id: list[int] | None = None,
    country: list[str] | None = None,
    level_id: list[int] | None = None,
    employment_type: list[str] | None = None,
    status: list[str] | None = None,
    band_position: list[str] | None = None,
    salary_band: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build a parameterised WHERE clause + bind params.

    Each filter accepts a LIST of values (multi-select). When the list
    is empty or None the filter is dropped entirely. `band_position`
    requires the caller to have joined `employees_current_salary` (as
    `ecs`) and `comp_bands` (as `cb`) — see `_LIST_FROM` below.

    Postgres `= ANY(:values)` does the heavy lifting; psycopg adapts
    Python lists to Postgres ARRAY[...] automatically.
    """
    conds: list[str] = []
    params: dict[str, Any] = {}

    if q:
        conds.append(
            "(lower(e.first_name || ' ' || e.last_name) LIKE :q " "OR lower(e.email) LIKE :q)"
        )
        params["q"] = f"%{q.lower()}%"
    if dept_id:
        conds.append("e.department_id = ANY(:dept_id)")
        params["dept_id"] = dept_id
    if country:
        conds.append("e.country = ANY(:country)")
        params["country"] = country
    if level_id:
        conds.append("e.level_id = ANY(:level_id)")
        params["level_id"] = level_id
    if employment_type:
        conds.append("e.employment_type = ANY(:employment_type)")
        params["employment_type"] = employment_type
    if status:
        conds.append("e.status = ANY(:status)")
        params["status"] = status
    if band_position:
        conds.append(
            "(CASE "
            "  WHEN ecs.amount IS NULL OR cb.band_min IS NULL THEN NULL "
            "  WHEN ecs.amount < cb.band_min THEN 'below' "
            "  WHEN ecs.amount > cb.band_max THEN 'above' "
            "  ELSE 'within' "
            "END) = ANY(:band_position)"
        )
        params["band_position"] = band_position
    if salary_band:
        # USD-band bucketing. Same CASE pattern as band_position so
        # multi-select via `= ANY(:salary_band)` Just Works.
        conds.append(
            "(CASE "
            "  WHEN ecs.amount_usd IS NULL THEN NULL "
            "  WHEN ecs.amount_usd < 10000 THEN '0-10000' "
            "  WHEN ecs.amount_usd < 50000 THEN '10000-50000' "
            "  WHEN ecs.amount_usd < 100000 THEN '50000-100000' "
            "  WHEN ecs.amount_usd < 150000 THEN '100000-150000' "
            "  WHEN ecs.amount_usd < 200000 THEN '150000-200000' "
            "  WHEN ecs.amount_usd < 300000 THEN '200000-300000' "
            "  ELSE '300000+' "
            "END) = ANY(:salary_band)"
        )
        params["salary_band"] = salary_band

    return " AND ".join(conds), params


# --- Query executors -----------------------------------------------------


# Shared FROM + JOINS used by both the list query and the count query.
# Joining comp_bands always (not just when filtering by band_position)
# costs nothing measurable at 10k rows and keeps the count query honest
# when band_position is filtered.
_LIST_FROM = """
FROM employees e
JOIN departments d ON d.id = e.department_id
JOIN levels      l ON l.id = e.level_id
LEFT JOIN employees_current_salary ecs ON ecs.employee_id = e.id
LEFT JOIN comp_bands cb ON cb.level_id = e.level_id AND cb.country = e.country
"""

_LIST_COLUMNS = """
SELECT
    e.id::text                AS id,
    e.employee_no,
    e.first_name,
    e.last_name,
    e.email,
    e.country,
    d.name                    AS department,
    l.code                    AS level,
    e.employment_type,
    e.status,
    e.hire_date,
    e.manager_id::text        AS manager_id,
    ecs.amount                AS current_amount,
    ecs.currency_code         AS current_currency,
    ecs.amount_usd            AS current_amount_usd,
    ecs.effective_date        AS current_effective_date,
    CASE
        WHEN ecs.amount IS NULL OR cb.band_min IS NULL THEN NULL
        WHEN ecs.amount < cb.band_min THEN 'below'
        WHEN ecs.amount > cb.band_max THEN 'above'
        ELSE 'within'
    END                       AS band_position
"""


def list_employees(
    session: Session,
    *,
    page: int,
    size: int,
    sort: str | None,
    q: str | None = None,
    dept_id: list[int] | None = None,
    country: list[str] | None = None,
    level_id: list[int] | None = None,
    employment_type: list[str] | None = None,
    status: list[str] | None = None,
    band_position: list[str] | None = None,
    salary_band: list[str] | None = None,
) -> tuple[list[dict], int]:
    """Return (rows, total). Caller maps rows to Pydantic models."""
    column, direction = parse_sort(sort)
    where_body, params = build_filters(
        q=q,
        dept_id=dept_id,
        country=country,
        level_id=level_id,
        employment_type=employment_type,
        status=status,
        band_position=band_position,
        salary_band=salary_band,
    )

    where_clause = f"WHERE {where_body}" if where_body else ""
    # `column` and `direction` come from a whitelist; `q` and the rest are
    # bound params. No string-interp injection surface.
    list_sql = (
        f"{_LIST_COLUMNS} {_LIST_FROM} {where_clause} "
        f"ORDER BY {column} {direction}, e.id "
        f"LIMIT :limit OFFSET :offset"
    )
    count_sql = f"SELECT count(*) {_LIST_FROM} {where_clause}"

    params_list = {**params, "limit": size, "offset": (page - 1) * size}

    rows = session.execute(text(list_sql), params_list).mappings().all()
    total = session.execute(text(count_sql), params).scalar_one()
    return [dict(r) for r in rows], int(total)


def iter_employees_for_export(
    session: Session,
    *,
    sort: str | None,
    q: str | None = None,
    dept_id: list[int] | None = None,
    country: list[str] | None = None,
    level_id: list[int] | None = None,
    employment_type: list[str] | None = None,
    status: list[str] | None = None,
    band_position: list[str] | None = None,
    salary_band: list[str] | None = None,
) -> Iterator[dict]:
    """Return an iterator over rows matching the filter + sort, no pagination.

    Validation (parse_sort) runs **eagerly** — if `sort` is invalid this
    raises ValueError before any iteration starts, so the route handler
    can convert it to a 400 instead of crashing mid-stream after
    StreamingResponse headers have already been sent.

    The inner `_iter` generator does the lazy row-by-row yield so we
    never materialize the full result set in memory.
    """
    column, direction = parse_sort(sort)
    where_body, params = build_filters(
        q=q,
        dept_id=dept_id,
        country=country,
        level_id=level_id,
        employment_type=employment_type,
        status=status,
        band_position=band_position,
        salary_band=salary_band,
    )
    where_clause = f"WHERE {where_body}" if where_body else ""
    sql = f"{_LIST_COLUMNS} {_LIST_FROM} {where_clause} " f"ORDER BY {column} {direction}, e.id"
    result = session.execute(text(sql), params).mappings()

    def _iter() -> Iterator[dict]:
        for row in result:
            yield dict(row)

    return _iter()


def get_employee_detail(session: Session, employee_id: str) -> dict | None:
    """Return the employee + manager + direct-reports count + current
    salary + band_position. Salary history / equity grants are fetched
    separately."""
    sql = """
        SELECT
            e.id::text                AS id,
            e.employee_no,
            e.first_name,
            e.last_name,
            e.email,
            e.country,
            e.department_id,
            d.name                    AS department,
            e.level_id,
            l.code                    AS level,
            e.employment_type,
            e.status,
            e.hire_date,
            mgr.id::text              AS manager_id_raw,
            mgr.employee_no           AS manager_no,
            mgr.first_name            AS manager_first_name,
            mgr.last_name             AS manager_last_name,
            (SELECT count(*) FROM employees r WHERE r.manager_id = e.id)
                                      AS direct_reports_count,
            ecs.amount                AS current_amount,
            ecs.currency_code         AS current_currency,
            ecs.amount_usd            AS current_amount_usd,
            ecs.effective_date        AS current_effective_date,
            CASE
                WHEN ecs.amount IS NULL OR cb.band_min IS NULL THEN NULL
                WHEN ecs.amount < cb.band_min THEN 'below'
                WHEN ecs.amount > cb.band_max THEN 'above'
                ELSE 'within'
            END                       AS band_position
        FROM employees e
        JOIN departments d ON d.id = e.department_id
        JOIN levels      l ON l.id = e.level_id
        LEFT JOIN employees mgr ON mgr.id = e.manager_id
        LEFT JOIN employees_current_salary ecs ON ecs.employee_id = e.id
        LEFT JOIN comp_bands cb ON cb.level_id = e.level_id AND cb.country = e.country
        WHERE e.id = :id
    """
    row = session.execute(text(sql), {"id": employee_id}).mappings().one_or_none()
    return dict(row) if row else None


def get_salary_history(session: Session, employee_id: str) -> list[dict]:
    sql = """
        SELECT
            sc.id::text                       AS id,
            sc.effective_date,
            sc.amount,
            sc.currency_code,
            (sc.amount / c.ratio_to_usd)::numeric(14, 2) AS amount_usd,
            sc.reason,
            sc.note,
            sc.created_at::date               AS created_at
        FROM salary_changes sc
        JOIN currencies c ON c.code = sc.currency_code
        WHERE sc.employee_id = :id
        ORDER BY sc.effective_date DESC, sc.id DESC
    """
    return [dict(r) for r in session.execute(text(sql), {"id": employee_id}).mappings().all()]


def get_equity_grants(session: Session, employee_id: str) -> list[dict]:
    sql = """
        SELECT
            id::text         AS id,
            grant_date,
            shares,
            created_at::date AS created_at
        FROM equity_grants
        WHERE employee_id = :id
        ORDER BY grant_date DESC, id DESC
    """
    return [dict(r) for r in session.execute(text(sql), {"id": employee_id}).mappings().all()]


def get_total_shares(session: Session, employee_id: str) -> int:
    sql = "SELECT COALESCE(SUM(shares), 0) FROM equity_grants WHERE employee_id = :id"
    return int(session.execute(text(sql), {"id": employee_id}).scalar_one())


# --- Mutating queries ----------------------------------------------------


_UPDATABLE_COLUMNS = (
    "department_id",
    "level_id",
    "manager_id",
    "employment_type",
    "status",
)


def update_employee(session: Session, employee_id: str, updates: dict[str, Any]) -> bool:
    """Apply PATCH updates. Returns True if a row was updated.

    Filters `updates` to the whitelist of columns we allow PATCHing.
    The column names go straight into the SQL string — they're keys of
    a whitelisted set, so no injection surface.
    """
    cleaned = {k: v for k, v in updates.items() if k in _UPDATABLE_COLUMNS}
    if not cleaned:
        return False

    set_clause = ", ".join(f"{col} = :{col}" for col in cleaned)
    sql = f"UPDATE employees SET {set_clause} WHERE id = :id"
    result = session.execute(text(sql), {**cleaned, "id": employee_id})
    return (result.rowcount or 0) > 0


def insert_salary_change(
    session: Session,
    *,
    employee_id: str,
    effective_date: Any,
    amount: Any,
    currency_code: str,
    reason: str,
    note: str | None,
    created_by: str,
) -> dict:
    sql = """
        INSERT INTO salary_changes
            (employee_id, effective_date, amount, currency_code, reason, note, created_by)
        VALUES
            (:employee_id, :effective_date, :amount, :currency_code, :reason, :note, :created_by)
        RETURNING
            id::text          AS id,
            effective_date,
            amount,
            currency_code,
            (amount / (SELECT ratio_to_usd FROM currencies WHERE code = :currency_code))
                ::numeric(14, 2) AS amount_usd,
            reason,
            note,
            created_at::date  AS created_at
    """
    row = (
        session.execute(
            text(sql),
            {
                "employee_id": employee_id,
                "effective_date": effective_date,
                "amount": amount,
                "currency_code": currency_code,
                "reason": reason,
                "note": note,
                "created_by": created_by,
            },
        )
        .mappings()
        .one()
    )
    return dict(row)


def insert_equity_grant(
    session: Session,
    *,
    employee_id: str,
    grant_date: Any,
    shares: int,
    created_by: str,
) -> dict:
    sql = """
        INSERT INTO equity_grants (employee_id, grant_date, shares, created_by)
        VALUES (:employee_id, :grant_date, :shares, :created_by)
        RETURNING
            id::text          AS id,
            grant_date,
            shares,
            created_at::date  AS created_at
    """
    row = (
        session.execute(
            text(sql),
            {
                "employee_id": employee_id,
                "grant_date": grant_date,
                "shares": shares,
                "created_by": created_by,
            },
        )
        .mappings()
        .one()
    )
    return dict(row)


def employee_exists(session: Session, employee_id: str) -> bool:
    row = session.execute(
        text("SELECT 1 FROM employees WHERE id = :id"), {"id": employee_id}
    ).scalar_one_or_none()
    return row is not None
