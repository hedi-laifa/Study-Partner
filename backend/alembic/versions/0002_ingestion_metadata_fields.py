"""Add ingestion warnings and page-range chunk metadata columns.

Revision ID: 0002_ingestion_metadata_fields
Revises: 0001_initial_schema
Create Date: 2026-11-03 19:42:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_ingestion_metadata_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "extraction_warnings",
                JSONVariant,
                nullable=False,
                server_default="[]",
            )
        )

    with op.batch_alter_table("chunk_metadata") as batch_op:
        batch_op.drop_index("ix_chunk_metadata_doc_page")
        batch_op.alter_column(
            "text_content",
            new_column_name="chunk_text",
            existing_type=sa.Text(),
             existing_nullable=False,
        )
        batch_op.add_column(sa.Column("page_start", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("page_end", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("section_title", sa.String(length=255), nullable=True)
        )
        batch_op.create_index(
            "ix_chunk_metadata_doc_page", ["document_id", "page_start"], unique=False
        )
        batch_op.create_index(
            "ix_chunk_metadata_doc_index", ["document_id", "chunk_index"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("chunk_metadata") as batch_op:
        batch_op.drop_index("ix_chunk_metadata_doc_index")
        batch_op.drop_index("ix_chunk_metadata_doc_page")
        batch_op.drop_column("section_title")
        batch_op.drop_column("page_end")
        batch_op.drop_column("page_start")
        batch_op.alter_column(
            "chunk_text",
            new_column_name="text_content",
            existing_type=sa.Text(),
            existing_nullable=False,
        )
        batch_op.create_index(
            "ix_chunk_metadata_doc_page", ["document_id", "page_number"], unique=False
        )

    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("extraction_warnings")
