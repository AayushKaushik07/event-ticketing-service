from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # discard connections the server already closed
    pool_recycle=3600,    # MySQL closes idle connections (wait_timeout); recycle first
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """One session per request.

    The close() in the finally block rolls back anything uncommitted, which
    means a row lock is always released even if a handler raises.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
