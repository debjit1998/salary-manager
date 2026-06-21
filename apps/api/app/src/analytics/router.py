"""Analytics endpoints — one per tool.

Each endpoint is a thin shim that:
  1. Validates request params via Pydantic
  2. Calls the matching function in queries.py
  3. Validates the response via Pydantic before returning

The same functions are reused by the NL-query endpoint (Task #8). All
endpoints behind get_current_user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.src.analytics import queries as q
from app.src.analytics.schemas import (
    AvgSalaryByResult,
    CompRatioVsBandResult,
    Dimension,
    EmployeeFilters,
    HeadcountByResult,
    HeadcountChangeRequest,
    HeadcountChangeResult,
    RaisesInPeriodRequest,
    RaisesInPeriodResult,
    SalaryDistributionResult,
    TopEarnersRequest,
    TopEarnersResult,
)
from app.src.common.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _filters_from_query(
    country: str | None = Query(None, pattern="^(US|UK|IN)$"),
    department_id: int | None = Query(None),
    level_id: int | None = Query(None),
    employment_type: str | None = Query(
        None, pattern="^(full_time|part_time|contractor)$"
    ),
    status: str | None = Query(
        "active", pattern="^(active|terminated)$"
    ),
) -> EmployeeFilters:
    """Reusable dependency that gathers the standard employee filters
    from query string into an EmployeeFilters model."""
    return EmployeeFilters(
        country=country,
        department_id=department_id,
        level_id=level_id,
        employment_type=employment_type,
        status=status,
    )


@router.get("/headcount-by", response_model=HeadcountByResult)
def headcount_by(
    dimension: Dimension,
    filters: EmployeeFilters = Depends(_filters_from_query),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> HeadcountByResult:
    try:
        result = q.headcount_by(session, dimension=dimension, filters=filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HeadcountByResult(**result)


@router.get("/avg-salary-by", response_model=AvgSalaryByResult)
def avg_salary_by(
    dimension: Dimension,
    filters: EmployeeFilters = Depends(_filters_from_query),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> AvgSalaryByResult:
    try:
        result = q.avg_salary_by(session, dimension=dimension, filters=filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AvgSalaryByResult(**result)


@router.get("/salary-distribution", response_model=SalaryDistributionResult)
def salary_distribution(
    filters: EmployeeFilters = Depends(_filters_from_query),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> SalaryDistributionResult:
    return SalaryDistributionResult(**q.salary_distribution(session, filters=filters))


@router.post("/top-earners", response_model=TopEarnersResult)
def top_earners(
    body: TopEarnersRequest,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> TopEarnersResult:
    return TopEarnersResult(
        **q.top_n_earners(session, n=body.n, filters=body.filters)
    )


@router.get("/comp-ratio-vs-band", response_model=CompRatioVsBandResult)
def comp_ratio_vs_band(
    filters: EmployeeFilters = Depends(_filters_from_query),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> CompRatioVsBandResult:
    return CompRatioVsBandResult(**q.comp_ratio_vs_band(session, filters=filters))


@router.post("/raises-in-period", response_model=RaisesInPeriodResult)
def raises_in_period(
    body: RaisesInPeriodRequest,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> RaisesInPeriodResult:
    if body.start > body.end:
        raise HTTPException(status_code=400, detail="start must be <= end")
    return RaisesInPeriodResult(
        **q.raises_in_period(
            session, start=body.start, end=body.end, filters=body.filters
        )
    )


@router.post("/headcount-change", response_model=HeadcountChangeResult)
def headcount_change(
    body: HeadcountChangeRequest,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(get_current_user),
) -> HeadcountChangeResult:
    if body.start > body.end:
        raise HTTPException(status_code=400, detail="start must be <= end")
    try:
        result = q.headcount_change(
            session, start=body.start, end=body.end, dimension=body.dimension
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HeadcountChangeResult(**result)
