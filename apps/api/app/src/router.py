"""Top-level router — aggregates every domain router into one
APIRouter that main.py mounts on the FastAPI app.

Adding a new domain (e.g. analytics) is a one-line include_router
here, keeping main.py free of per-domain knowledge.
"""

from fastapi import APIRouter

from app.src.analytics.router import router as analytics_router
from app.src.employee.router import router as employee_router
from app.src.user.router import router as user_router

router = APIRouter()
router.include_router(user_router)
router.include_router(employee_router)
router.include_router(analytics_router)
