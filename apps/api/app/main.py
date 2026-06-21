import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.settings import settings
from app.src.router import router as api_router


class _HealthCheckFilter(logging.Filter):
    """Suppress uvicorn access-log lines for the healthcheck endpoints.

    Docker pings /health every 10s; without this filter the access log
    is unreadable. The healthcheck itself still runs — only the log line
    is dropped.
    """

    _NOISY = (" /health ", " /health/db ")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(p in msg for p in self._NOISY)


logging.getLogger("uvicorn.access").addFilter(_HealthCheckFilter())


app = FastAPI(title="Salary Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db(session: Session = Depends(get_session)) -> dict[str, object]:
    row = session.execute(text("SELECT 1 AS ok")).mappings().one()
    return {"db": "up", "result": dict(row)}


app.include_router(api_router)
