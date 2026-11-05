"""Database engine, declarative base, session management, and connection validation."""
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.logging import logger


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy 2.0 ORM models."""


def _configure_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enable foreign key constraint enforcement when using SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def build_engine(database_url: str | None = None) -> Engine:
    """Create a configured SQLAlchemy Engine for PostgreSQL or SQLite."""
    url = database_url or settings.DATABASE_URL
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.DB_ECHO,
        )
        event.listen(engine, "connect", _configure_sqlite_pragma)
        return engine

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        echo=settings.DB_ECHO,
    )


@lru_cache
def get_engine() -> Engine:
    """Create and cache the default SQLAlchemy engine lazily."""
    return build_engine(settings.DATABASE_URL)


def get_session_local() -> sessionmaker[Session]:
    """Return a configured sessionmaker bound to the active engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional SQLAlchemy database session."""
    session_factory = get_session_local()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of database operations."""
    session_factory = get_session_local()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def validate_database_connection(db: Session | None = None) -> tuple[bool, str]:
    """Verify database connectivity by executing a lightweight SELECT 1 query."""
    try:
        if db is not None:
            db.execute(text("SELECT 1"))
            return True, "connected"
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "connected"
    except (SQLAlchemyError, ModuleNotFoundError, Exception) as exc:
        logger.warning(f"Database connection validation failed: {exc}")
        return False, str(exc)
