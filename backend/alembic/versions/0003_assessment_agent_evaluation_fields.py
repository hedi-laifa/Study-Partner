"""Add Phase 6 Assessment Agent fields to evaluations table.

Revision ID: 0003_assessment_agent_evaluation_fields
Revises: 0002_ingestion_metadata_fields
Create Date: 2026-11-03 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_assessment_agent_evaluation_fields"
down_revision: Union[str, None] = "0002_ingestion_metadata_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.add_column(sa.Column("concept_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "verdict",
                sa.String(length=40),
                nullable=False,
                server_default="INCORRECT",
            )
        )
        batch_op.add_column(sa.Column("misconception", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "evidence_json",
                JSONVariant,
                nullable=False,
                server_default="[]",
            )
        )
        batch_op.add_column(
            sa.Column(
                "confidence",
                sa.Float(),
                nullable=False,
                server_default="0.85",
            )
        )
        batch_op.add_column(
            sa.Column("next_activity", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "error_classification",
                sa.String(length=40),
                nullable=False,
                server_default="NONE",
            )
        )
        batch_op.add_column(
            sa.Column(
                "uncertain_evaluation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column("prompt_version", sa.String(length=40), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_evaluations_concept_id_concepts",
            "concepts",
            ["concept_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_evaluations_concept_id", ["concept_id"], unique=False)
        batch_op.create_index("ix_evaluations_verdict", ["verdict"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_index("ix_evaluations_verdict")
        batch_op.drop_index("ix_evaluations_concept_id")
        batch_op.drop_constraint(
            "fk_evaluations_concept_id_concepts", type_="foreignkey"
        )
        batch_op.drop_column("prompt_version")
        batch_op.drop_column("uncertain_evaluation")
        batch_op.drop_column("error_classification")
        batch_op.drop_column("next_activity")
        batch_op.drop_column("confidence")
        batch_op.drop_column("evidence_json")
        batch_op.drop_column("misconception")
        batch_op.drop_column("verdict")
        batch_op.drop_column("concept_id")
