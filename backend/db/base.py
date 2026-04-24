"""SQLAlchemy engine, session, and declarative base."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base that all ORM models inherit from."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session.

    The session is closed automatically once the request handler returns,
    regardless of success or failure.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
