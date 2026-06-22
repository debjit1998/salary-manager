"""SQL + pure helpers for the 7 analytics tools.

Each tool is a function with a tightly-typed signature so it can be
called both from the analytics router and from the NL-query endpoint
(Task #8) — Claude picks a tool, the backend calls the matching
function with the validated args.

All tools take an optional `EmployeeFilters` (country / dept / level /
employment_type / status). Filter values are bound parameters; only
the `dimension` and sort columns are string-interpolated, and both go
through a whitelist.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.src.common.schemas import EmployeeFilters

# --- Dimension whitelist (safe to interpolate; values are static) --------

_DIMENSION_SPEC: dict[str, dict[str, str]] = {
    "department": {
        "select": "d.name",
        "join": "JOIN departments d ON d.id = e.department_id",
        "group_by": "d.name",
        "order_by": "count DESC, d.name ASC",
    },
    "level": {
        "select": "l.code",
        "join": "JOIN levels l ON l.id = e.level_id",
        "group_by": "l.code, l.rank",
        "order_by": "l.rank ASC",
    },
    "country": {
        "select": "e.country",
        "join": "",
        "group_by": "e.country",
        "order_by": "count DESC, e.country ASC",
    },
    "employment_type": {
        "select": "e.employment_type",
        "join": "",
        "group_by": "e.employment_type",
        "order_by": "count DESC, e.employment_type ASC",
    },
}


def _dimension(name: str) -> dict[str, str]:
    spec = _DIMENSION_SPEC.get(name)
    if spec is None:
        raise ValueError(f"unsupported dimension: {name!r}. valid: {sorted(_DIMENSION_SPEC)}")
    return spec


def _build_employee_where(
    filters: EmployeeFilters | None, *, alias: str = "e"
) -> tuple[str, dict[str, Any]]:
    """Build a WHERE body (no 'WHERE' prefix) from EmployeeFilters.

    Every filter uses `= ANY(:bind)` so the same code path handles
    single-value and multi-select input. Status defaults to 'active'
    when not provided (the common case for the dashboard).

    `salary_band` and `band_position` require the calling query to have
    LEFT-JOINed `employees_current_salary` (alias `ecs`) and
    `comp_bands` (alias `cb`). The analytics functions below do that
    by default."""
    if filters is None:
        filters = EmployeeFilters()
    conds: list[str] = []
    params: dict[str, Any] = {}

    # Status default — applied inline when no filter, no bind parameter.
    if filters.status:
        conds.append(f"{alias}.status = ANY(:status)")
        params["status"] = filters.status
    else:
        conds.append(f"{alias}.status = 'active'")
    if filters.country:
        conds.append(f"{alias}.country = ANY(:country)")
        params["country"] = filters.country
    if filters.department_id:
        conds.append(f"{alias}.department_id = ANY(:department_id)")
        params["department_id"] = filters.department_id
    if filters.level_id:
        conds.append(f"{alias}.level_id = ANY(:level_id)")
        params["level_id"] = filters.level_id
    if filters.employment_type:
        conds.append(f"{alias}.employment_type = ANY(:employment_type)")
        params["employment_type"] = filters.employment_type
    if filters.salary_band:
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
        params["salary_band"] = filters.salary_band
    if filters.band_position:
        conds.append(
            "(CASE "
            "  WHEN ecs.amount IS NULL OR cb.band_min IS NULL THEN NULL "
            "  WHEN ecs.amount < cb.band_min THEN 'below' "
            "  WHEN ecs.amount > cb.band_max THEN 'above' "
            "  ELSE 'within' "
            "END) = ANY(:band_position)"
        )
        params["band_position"] = filters.band_position
    return " AND ".join(conds), params


# JOIN clauses for the salary view and comp bands — used by every
# analytics function so all seven filters work uniformly.
_FILTER_JOINS = """
LEFT JOIN employees_current_salary ecs ON ecs.employee_id = e.id
LEFT JOIN comp_bands cb ON cb.level_id = e.level_id AND cb.country = e.country
"""


# --- Tool 1: headcount_by ------------------------------------------------


def headcount_by(
    session: Session, *, dimension: str, filters: EmployeeFilters | None = None
) -> dict:
    spec = _dimension(dimension)
    where, params = _build_employee_where(filters)
    sql = f"""
        SELECT {spec['select']} AS dimension, count(*) AS count
        FROM employees e
        {spec['join']}
        {_FILTER_JOINS}
        WHERE {where}
        GROUP BY {spec['group_by']}
        ORDER BY {spec['order_by']}
    """
    rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]
    total = sum(r["count"] for r in rows)
    return {"rows": rows, "dimension": dimension, "total": total}


# --- Tool 2: avg_salary_by ----------------------------------------------


def avg_salary_by(
    session: Session, *, dimension: str, filters: EmployeeFilters | None = None
) -> dict:
    spec = _dimension(dimension)
    where, params = _build_employee_where(filters)
    sql = f"""
        SELECT
            {spec['select']} AS dimension,
            avg(ecs.amount_usd)::numeric(14, 2) AS avg_salary_usd,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY ecs.amount_usd)::numeric(14, 2)
                AS median_salary_usd,
            count(*) AS count
        FROM employees e
        {spec['join']}
        {_FILTER_JOINS}
        WHERE {where}
        GROUP BY {spec['group_by']}
        ORDER BY {spec['order_by']}
    """
    rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]
    return {"rows": rows, "dimension": dimension}


# --- Tool 3: salary_distribution ----------------------------------------

# Fixed USD buckets. The top bucket has upper=None to signal open-ended.
_SALARY_BUCKETS: list[tuple[str, int, int | None]] = [
    ("0-50k", 0, 50_000),
    ("50-100k", 50_000, 100_000),
    ("100-150k", 100_000, 150_000),
    ("150-200k", 150_000, 200_000),
    ("200-300k", 200_000, 300_000),
    ("300-500k", 300_000, 500_000),
    ("500k+", 500_000, None),
]


def salary_distribution(session: Session, *, filters: EmployeeFilters | None = None) -> dict:
    where, params = _build_employee_where(filters)
    sql = f"""
        SELECT ecs.amount_usd
        FROM employees e
        {_FILTER_JOINS}
        WHERE {where}
          AND ecs.amount_usd IS NOT NULL
    """
    amounts = [r[0] for r in session.execute(text(sql), params).all()]

    buckets: list[dict] = []
    for label, lower, upper in _SALARY_BUCKETS:
        if upper is None:
            count = sum(1 for a in amounts if a >= lower)
        else:
            count = sum(1 for a in amounts if lower <= a < upper)
        buckets.append({"label": label, "lower_usd": lower, "upper_usd": upper, "count": count})
    return {"buckets": buckets, "total": len(amounts)}


# --- Tool 4: top_n_earners ----------------------------------------------


def top_n_earners(
    session: Session,
    *,
    n: int = 10,
    filters: EmployeeFilters | None = None,
) -> dict:
    where, params = _build_employee_where(filters)
    params["n"] = n
    sql = f"""
        SELECT
            e.id::text                AS id,
            e.employee_no,
            e.first_name,
            e.last_name,
            e.country,
            d.name                    AS department,
            l.code                    AS level,
            ecs.amount_usd,
            ecs.amount                AS amount_native,
            ecs.currency_code
        FROM employees e
        JOIN departments d ON d.id = e.department_id
        JOIN levels      l ON l.id = e.level_id
        {_FILTER_JOINS}
        WHERE {where}
          AND ecs.amount_usd IS NOT NULL
        ORDER BY ecs.amount_usd DESC, e.employee_no ASC
        LIMIT :n
    """
    rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]
    return {"rows": rows}


# --- Tool 5: comp_ratio_vs_band -----------------------------------------


def comp_ratio_vs_band(session: Session, *, filters: EmployeeFilters | None = None) -> dict:
    where, params = _build_employee_where(filters)
    sql = f"""
        WITH labelled AS (
            SELECT
                e.id::text                                AS id,
                e.employee_no,
                e.first_name,
                e.last_name,
                e.country,
                d.name                                    AS department,
                l.code                                    AS level,
                ecs.amount,
                ecs.currency_code,
                cb.band_min,
                cb.band_max,
                CASE
                    WHEN ecs.amount < cb.band_min THEN 'below'
                    WHEN ecs.amount > cb.band_max THEN 'above'
                    ELSE 'within'
                END                                       AS band_position
            FROM employees e
            JOIN employees_current_salary ecs ON ecs.employee_id = e.id
            JOIN departments d ON d.id = e.department_id
            JOIN levels      l ON l.id = e.level_id
            JOIN comp_bands  cb ON cb.level_id = e.level_id AND cb.country = e.country
            WHERE {where}
        )
        SELECT * FROM labelled
    """
    rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]

    summary = {"below": 0, "within": 0, "above": 0}
    out_of_band: list[dict] = []
    for r in rows:
        summary[r["band_position"]] += 1
        if r["band_position"] != "within":
            out_of_band.append(r)
    # Order out-of-band by below first, then most extreme deviation
    out_of_band.sort(
        key=lambda r: (
            0 if r["band_position"] == "below" else 1,
            -float(r["amount"]) if r["band_position"] == "below" else float(r["amount"]),
        )
    )
    return {"summary": summary, "out_of_band": out_of_band}


# --- Tool 6: raises_in_period -------------------------------------------


def raises_in_period(
    session: Session,
    *,
    start: date,
    end: date,
    filters: EmployeeFilters | None = None,
) -> dict:
    where, params = _build_employee_where(filters)
    params["start"] = start
    params["end"] = end
    sql = f"""
        SELECT
            sc.id::text          AS id,
            e.id::text           AS employee_id,
            e.employee_no,
            e.first_name,
            e.last_name,
            e.country,
            d.name               AS department,
            l.code               AS level,
            sc.effective_date,
            sc.amount,
            sc.currency_code,
            (sc.amount / c.ratio_to_usd)::numeric(14, 2) AS amount_usd,
            sc.reason,
            sc.note
        FROM salary_changes sc
        JOIN employees   e ON e.id = sc.employee_id
        JOIN currencies  c ON c.code = sc.currency_code
        JOIN departments d ON d.id = e.department_id
        JOIN levels      l ON l.id = e.level_id
        WHERE sc.effective_date BETWEEN :start AND :end
          AND sc.reason IN ('raise', 'promo')
          AND {where}
        ORDER BY sc.effective_date DESC, e.employee_no ASC
    """
    rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]
    return {"rows": rows, "count": len(rows), "start": start, "end": end}


# --- Tool 7: headcount_change -------------------------------------------


def headcount_change(
    session: Session,
    *,
    start: date,
    end: date,
    dimension: str,
) -> dict:
    spec = _dimension(dimension)
    # spec['order_by'] references 'count' which only exists in the count-
    # by queries. headcount_change has different columns, so order by the
    # dimension itself (rank for level so L3/L4/.../L10 sort numerically).
    order_by = "l.rank ASC" if dimension == "level" else spec["select"]
    # Only count active employees here — terminated rows would otherwise
    # appear in 'before_start' but be missing from 'total_through_end',
    # making the numbers confusing.
    sql = f"""
        SELECT
            {spec['select']} AS dimension,
            count(*) FILTER (WHERE e.hire_date < :start)        AS before_start,
            count(*) FILTER (
                WHERE e.hire_date BETWEEN :start AND :end
            )                                                   AS hired_in_period,
            count(*) FILTER (WHERE e.hire_date <= :end)         AS total_through_end
        FROM employees e
        {spec['join']}
        WHERE e.status = 'active'
        GROUP BY {spec['group_by']}
        ORDER BY {order_by}
    """
    rows = [
        dict(r) for r in session.execute(text(sql), {"start": start, "end": end}).mappings().all()
    ]
    return {"rows": rows, "dimension": dimension, "start": start, "end": end}


# --- Summary (dashboard KPI tiles) ---------------------------------------


def summary(session: Session) -> dict:
    """All four dashboard KPI tile values in a single round-trip.

    Computed inline rather than via the other tools because each tile
    has a different shape and we want one query, not four.
    """
    sql = """
        SELECT
            (SELECT count(*) FROM employees WHERE status = 'active')
                AS active_headcount,
            (SELECT coalesce(avg(ecs.amount_usd), 0)::numeric(14, 2)
             FROM employees e
             JOIN employees_current_salary ecs ON ecs.employee_id = e.id
             WHERE e.status = 'active')
                AS avg_salary_usd,
            (SELECT count(*)
             FROM employees e
             JOIN employees_current_salary ecs ON ecs.employee_id = e.id
             JOIN comp_bands cb ON cb.level_id = e.level_id AND cb.country = e.country
             WHERE e.status = 'active'
               AND ecs.amount < cb.band_min)
                AS below_band_count,
            (SELECT count(*) FROM employees
             WHERE status = 'active'
               AND hire_date >= CURRENT_DATE - INTERVAL '90 days')
                AS hires_last_90_days
    """
    row = session.execute(text(sql)).mappings().one()
    return dict(row)
