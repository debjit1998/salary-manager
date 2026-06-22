"""Employee + salary-change + equity-grant endpoints.

All routes require an authenticated HR user. CRUD on the directory,
plus append-only writes to the salary and equity history tables.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.src.common.auth import CurrentUser, get_current_user
from app.src.employee import queries as q
from app.src.employee.schemas import (
    CurrentSalary,
    EmployeeDetail,
    EmployeeListItem,
    EmployeeListResponse,
    EmployeeUpdate,
    EquityGrantCreate,
    EquityGrantOut,
    ManagerSummary,
    SalaryChangeCreate,
    SalaryChangeOut,
)

router = APIRouter(prefix="/employees", tags=["employees"])


# --- Helpers -------------------------------------------------------------


def _list_row_to_item(row: dict) -> EmployeeListItem:
    current = (
        CurrentSalary(
            amount=row["current_amount"],
            currency_code=row["current_currency"],
            amount_usd=row["current_amount_usd"],
            effective_date=row["current_effective_date"],
        )
        if row["current_amount"] is not None
        else None
    )
    return EmployeeListItem(
        id=row["id"],
        employee_no=row["employee_no"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        country=row["country"],
        department=row["department"],
        level=row["level"],
        employment_type=row["employment_type"],
        status=row["status"],
        hire_date=row["hire_date"],
        manager_id=row["manager_id"],
        current_salary=current,
        band_position=row["band_position"],
    )


def _detail_row_to_model(
    row: dict,
    history: list[dict],
    grants: list[dict],
    total_shares: int,
) -> EmployeeDetail:
    current = (
        CurrentSalary(
            amount=row["current_amount"],
            currency_code=row["current_currency"],
            amount_usd=row["current_amount_usd"],
            effective_date=row["current_effective_date"],
        )
        if row["current_amount"] is not None
        else None
    )
    manager = (
        ManagerSummary(
            id=row["manager_id_raw"],
            employee_no=row["manager_no"],
            first_name=row["manager_first_name"],
            last_name=row["manager_last_name"],
        )
        if row["manager_id_raw"]
        else None
    )
    return EmployeeDetail(
        id=row["id"],
        employee_no=row["employee_no"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        country=row["country"],
        department_id=row["department_id"],
        department=row["department"],
        level_id=row["level_id"],
        level=row["level"],
        employment_type=row["employment_type"],
        status=row["status"],
        hire_date=row["hire_date"],
        manager=manager,
        direct_reports_count=row["direct_reports_count"],
        current_salary=current,
        band_position=row["band_position"],
        total_shares=total_shares,
        salary_changes=[SalaryChangeOut(**h) for h in history],
        equity_grants=[EquityGrantOut(**g) for g in grants],
    )


# --- Endpoints -----------------------------------------------------------


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    sort: str | None = Query(None, description="e.g. 'hire_date' or '-current_salary_usd'"),
    q_: str | None = Query(None, alias="q", description="search name or email"),
    # Multi-select: repeat the query param (`?country=US&country=UK`).
    # axios on the FE is configured with `paramsSerializer.indexes:null`
    # so it produces that exact format from an array.
    dept_id: list[int] | None = Query(None),
    country: list[str] | None = Query(None),
    level_id: list[int] | None = Query(None),
    employment_type: list[str] | None = Query(None),
    status_: list[str] | None = Query(None, alias="status"),
    band_position: list[str] | None = Query(None),
    salary_band: list[str] | None = Query(None),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> EmployeeListResponse:
    try:
        rows, total = q.list_employees(
            session,
            page=page,
            size=size,
            sort=sort,
            q=q_,
            dept_id=dept_id,
            country=country,
            level_id=level_id,
            employment_type=employment_type,
            status=status_,
            band_position=band_position,
            salary_band=salary_band,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EmployeeListResponse(
        items=[_list_row_to_item(r) for r in rows],
        page=page,
        size=size,
        total=total,
    )


# Column order in the CSV. Header strings here also drive the header row.
_EXPORT_COLUMNS: list[tuple[str, str]] = [
    ("employee_no", "employee_no"),
    ("first_name", "first_name"),
    ("last_name", "last_name"),
    ("email", "email"),
    ("country", "country"),
    ("department", "department"),
    ("level", "level"),
    ("employment_type", "employment_type"),
    ("status", "status"),
    ("hire_date", "hire_date"),
    ("current_amount", "current_salary_amount"),
    ("current_currency", "current_salary_currency"),
    ("current_amount_usd", "current_salary_usd"),
    ("current_effective_date", "salary_effective_date"),
    ("band_position", "band_position"),
]


def _row_to_csv_values(row: dict) -> list[str]:
    """Stringify a row for csv.writer — dates → ISO, None → empty string."""
    out: list[str] = []
    for src_key, _ in _EXPORT_COLUMNS:
        value = row.get(src_key)
        if value is None:
            out.append("")
        elif hasattr(value, "isoformat"):
            out.append(value.isoformat())
        else:
            out.append(str(value))
    return out


# Must be declared BEFORE the `/{employee_id}` route — FastAPI matches in
# declaration order, and otherwise `export.csv` would be parsed as an id.
@router.get("/export.csv")
def export_employees_csv(
    sort: str | None = Query(None),
    q_: str | None = Query(None, alias="q"),
    dept_id: list[int] | None = Query(None),
    country: list[str] | None = Query(None),
    level_id: list[int] | None = Query(None),
    employment_type: list[str] | None = Query(None),
    status_: list[str] | None = Query(None, alias="status"),
    band_position: list[str] | None = Query(None),
    salary_band: list[str] | None = Query(None),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Export the filtered+sorted employee list as CSV.

    Accepts the same query params as `GET /employees` minus page/size —
    returns every matching row. The response streams a chunk per row so
    we never hold the whole CSV in memory.
    """
    try:
        rows_iter = q.iter_employees_for_export(
            session,
            sort=sort,
            q=q_,
            dept_id=dept_id,
            country=country,
            level_id=level_id,
            employment_type=employment_type,
            status=status_,
            band_position=band_position,
            salary_band=salary_band,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def generate() -> Iterator[str]:
        buf = io.StringIO()
        writer = csv.writer(buf)

        writer.writerow([header for _, header in _EXPORT_COLUMNS])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate()

        for row in rows_iter:
            writer.writerow(_row_to_csv_values(row))
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    filename = f"employees-{date.today().isoformat()}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{employee_id}", response_model=EmployeeDetail)
def get_employee(
    employee_id: str,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> EmployeeDetail:
    row = q.get_employee_detail(session, employee_id)
    if row is None:
        raise HTTPException(status_code=404, detail="employee not found")
    history = q.get_salary_history(session, employee_id)
    grants = q.get_equity_grants(session, employee_id)
    total_shares = q.get_total_shares(session, employee_id)
    return _detail_row_to_model(row, history, grants, total_shares)


@router.patch("/{employee_id}", response_model=EmployeeDetail)
def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> EmployeeDetail:
    if not q.employee_exists(session, employee_id):
        raise HTTPException(status_code=404, detail="employee not found")

    updates = body.model_dump(exclude_unset=True)
    if updates:
        # Reject manager_id pointing at a non-existent employee or at self.
        if "manager_id" in updates and updates["manager_id"]:
            if updates["manager_id"] == employee_id:
                raise HTTPException(status_code=400, detail="manager_id cannot be self")
            if not q.employee_exists(session, updates["manager_id"]):
                raise HTTPException(status_code=400, detail="manager_id not found")
        q.update_employee(session, employee_id, updates)
        session.commit()

    return get_employee(employee_id, session=session, _user=_user)


@router.post(
    "/{employee_id}/salary-changes",
    response_model=SalaryChangeOut,
    status_code=status.HTTP_201_CREATED,
)
def add_salary_change(
    employee_id: str,
    body: SalaryChangeCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> SalaryChangeOut:
    if not q.employee_exists(session, employee_id):
        raise HTTPException(status_code=404, detail="employee not found")
    row = q.insert_salary_change(
        session,
        employee_id=employee_id,
        effective_date=body.effective_date,
        amount=body.amount,
        currency_code=body.currency_code,
        reason=body.reason,
        note=body.note,
        created_by=user.id,
    )
    # If the salary change includes a new level (FE sends this when
    # reason='promo'), bump the employee's level in the same
    # transaction so the row and the org state stay consistent.
    if body.new_level_id is not None:
        q.update_employee(session, employee_id, {"level_id": body.new_level_id})
    session.commit()
    return SalaryChangeOut(**row)


@router.post(
    "/{employee_id}/equity-grants",
    response_model=EquityGrantOut,
    status_code=status.HTTP_201_CREATED,
)
def add_equity_grant(
    employee_id: str,
    body: EquityGrantCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> EquityGrantOut:
    if not q.employee_exists(session, employee_id):
        raise HTTPException(status_code=404, detail="employee not found")
    row = q.insert_equity_grant(
        session,
        employee_id=employee_id,
        grant_date=body.grant_date,
        shares=body.shares,
        created_by=user.id,
    )
    session.commit()
    return EquityGrantOut(**row)
