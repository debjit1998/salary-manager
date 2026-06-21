from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.settings import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLAlchemy session."""
    with Session(engine) as session:
        yield session
