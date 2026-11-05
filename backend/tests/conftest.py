"""Shared pytest fixtures for database and FastAPI client testing."""
from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base, build_engine, get_db
from app.main import app


@pytest.fixture()
def db_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    """Create a temporary file-backed SQLite engine with foreign keys enabled."""
    db_file = tmp_path / "test_study_partner.db"
    engine = build_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Yield an isolated SQLAlchemy session bound to the test engine."""
    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Yield a FastAPI TestClient wired to the isolated test database session and storage."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", str(tmp_path / "chroma_test_store"))
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path / "uploads_test_store"))
    monkeypatch.setattr(settings, "TUTOR_OFFLINE_FALLBACK", True)
    monkeypatch.setattr(settings, "OLLAMA_TIMEOUT_SECONDS", 0.15)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

