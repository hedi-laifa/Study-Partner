"""Tests for Alembic database migrations (upgrade head, schema inspection, downgrade base)."""
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
    "users",
    "courses",
    "documents",
    "chunk_metadata",
    "concepts",
    "study_sessions",
    "activities",
    "attempts",
    "evaluations",
    "learning_evidences",
    "concept_progress",
    "revision_tasks",
}


def test_alembic_upgrade_and_downgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Alembic migrations apply cleanly to head and downgrade to base."""
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini_path = backend_dir / "alembic.ini"
    migration_db = tmp_path / "alembic_migration_test.db"
    db_url = f"sqlite:///{migration_db}"

    monkeypatch.setenv("DATABASE_URL", db_url)

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(existing_tables)

    # Verify key indexes exist
    user_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
    assert "ix_users_email" in user_indexes

    chunk_indexes = {idx["name"] for idx in inspector.get_indexes("chunk_metadata")}
    assert "ix_chunk_metadata_chroma_vector_id" in chunk_indexes

    engine.dispose()

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    remaining_tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert len(remaining_tables) == 0
    engine.dispose()

    # 3. Re-upgrade to head
    command.upgrade(alembic_cfg, "head")
