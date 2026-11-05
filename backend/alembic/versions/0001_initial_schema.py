"""Initial schema for all 12 Study Partner AI core models.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-03 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. courses
    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_courses_user_id", "courses", ["user_id"], unique=False)
    op.create_index("ix_courses_user_title", "courses", ["user_id", "title"], unique=False)

    # 3. documents
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "mime_type",
            sa.String(length=100),
            nullable=False,
            server_default="application/pdf",
        ),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status", sa.String(length=30), nullable=False, server_default="UPLOADED"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"], unique=False)
    op.create_index("ix_documents_course_id", "documents", ["course_id"], unique=False)
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)

    # 4. chunk_metadata (references ChromaDB vector id; does NOT store vector arrays)
    op.create_table(
        "chunk_metadata",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chroma_vector_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", JSONVariant, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_chunk_metadata_document_id", "chunk_metadata", ["document_id"], unique=False
    )
    op.create_index(
        "ix_chunk_metadata_course_id", "chunk_metadata", ["course_id"], unique=False
    )
    op.create_index(
        "ix_chunk_metadata_chroma_vector_id",
        "chunk_metadata",
        ["chroma_vector_id"],
        unique=True,
    )
    op.create_index(
        "ix_chunk_metadata_doc_page",
        "chunk_metadata",
        ["document_id", "page_number"],
        unique=False,
    )

    # 5. concepts
    op.create_table(
        "concepts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "course_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "difficulty",
            sa.String(length=30),
            nullable=False,
            server_default="INTERMEDIATE",
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_pages", JSONVariant, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_concepts_course_id", "concepts", ["course_id"], unique=False)
    op.create_index(
        "ix_concepts_source_document_id",
        "concepts",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_concepts_course_order",
        "concepts",
        ["course_id", "display_order"],
        unique=False,
    )

    # 6. study_sessions
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "current_concept_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="IDLE"),
        sa.Column("context_data", JSONVariant, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_study_sessions_user_id", "study_sessions", ["user_id"], unique=False
    )
    op.create_index(
        "ix_study_sessions_course_id", "study_sessions", ["course_id"], unique=False
    )
    op.create_index(
        "ix_study_sessions_current_concept_id",
        "study_sessions",
        ["current_concept_id"],
        unique=False,
    )
    op.create_index(
        "ix_study_sessions_state", "study_sessions", ["state"], unique=False
    )

    # 7. activities
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("study_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_type", sa.String(length=40), nullable=False),
        sa.Column(
            "difficulty",
            sa.String(length=30),
            nullable=False,
            server_default="INTERMEDIATE",
        ),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("rubric_json", JSONVariant, nullable=False),
        sa.Column("ideal_answer_summary", sa.Text(), nullable=True),
        sa.Column("source_chunk_ids", JSONVariant, nullable=False),
        sa.Column(
            "status", sa.String(length=30), nullable=False, server_default="ACTIVE"
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_activities_session_id", "activities", ["session_id"], unique=False
    )
    op.create_index(
        "ix_activities_concept_id", "activities", ["concept_id"], unique=False
    )
    op.create_index(
        "ix_activities_activity_type", "activities", ["activity_type"], unique=False
    )

    # 8. attempts
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "activity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attempts_activity_id", "attempts", ["activity_id"], unique=False)
    op.create_index("ix_attempts_user_id", "attempts", ["user_id"], unique=False)
    op.create_index(
        "ix_attempts_activity_attempt_num",
        "attempts",
        ["activity_id", "attempt_number"],
        unique=False,
    )

    # 9. evaluations
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "attempt_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("criteria_scores_json", JSONVariant, nullable=False),
        sa.Column("strengths_json", JSONVariant, nullable=False),
        sa.Column("gaps_json", JSONVariant, nullable=False),
        sa.Column("overall_feedback", sa.Text(), nullable=False),
        sa.Column("evaluator_model", sa.String(length=100), nullable=True),
        sa.Column("coach_action", sa.String(length=30), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_evaluations_attempt_id", "evaluations", ["attempt_id"], unique=False
    )
    op.create_index(
        "ix_evaluations_coach_action", "evaluations", ["coach_action"], unique=False
    )

    # 10. learning_evidences
    op.create_table(
        "learning_evidences",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("score_delta", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("observed_score", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONVariant, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_learning_evidences_user_id", "learning_evidences", ["user_id"], unique=False
    )
    op.create_index(
        "ix_learning_evidences_concept_id",
        "learning_evidences",
        ["concept_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_evidences_evaluation_id",
        "learning_evidences",
        ["evaluation_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_evidences_user_concept",
        "learning_evidences",
        ["user_id", "concept_id"],
        unique=False,
    )

    # 11. concept_progress
    op.create_table(
        "concept_progress",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mastery_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "mastery_status",
            sa.String(length=30),
            nullable=False,
            server_default="NOT_STARTED",
        ),
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "correct_attempts_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_score", sa.Float(), nullable=True),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "concept_id", name="uq_concept_progress_user_concept"
        ),
    )
    op.create_index(
        "ix_concept_progress_user_id", "concept_progress", ["user_id"], unique=False
    )
    op.create_index(
        "ix_concept_progress_course_id", "concept_progress", ["course_id"], unique=False
    )
    op.create_index(
        "ix_concept_progress_concept_id",
        "concept_progress",
        ["concept_id"],
        unique=False,
    )
    op.create_index(
        "ix_concept_progress_mastery_status",
        "concept_progress",
        ["mastery_status"],
        unique=False,
    )

    # 12. revision_tasks
    op.create_table(
        "revision_tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_evaluation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "priority", sa.String(length=20), nullable=False, server_default="MEDIUM"
        ),
        sa.Column(
            "status", sa.String(length=30), nullable=False, server_default="PENDING"
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_revision_tasks_user_id", "revision_tasks", ["user_id"], unique=False
    )
    op.create_index(
        "ix_revision_tasks_course_id", "revision_tasks", ["course_id"], unique=False
    )
    op.create_index(
        "ix_revision_tasks_concept_id", "revision_tasks", ["concept_id"], unique=False
    )
    op.create_index(
        "ix_revision_tasks_status", "revision_tasks", ["status"], unique=False
    )
    op.create_index(
        "ix_revision_tasks_priority", "revision_tasks", ["priority"], unique=False
    )
    op.create_index(
        "ix_revision_tasks_due_at", "revision_tasks", ["due_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("revision_tasks")
    op.drop_table("concept_progress")
    op.drop_table("learning_evidences")
    op.drop_table("evaluations")
    op.drop_table("attempts")
    op.drop_table("activities")
    op.drop_table("study_sessions")
    op.drop_table("concepts")
    op.drop_table("chunk_metadata")
    op.drop_table("documents")
    op.drop_table("courses")
    op.drop_table("users")
