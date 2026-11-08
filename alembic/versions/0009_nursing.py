"""add vital signs and nursing notes (护士站)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vital_signs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False
        ),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("pulse", sa.Integer(), nullable=True),
        sa.Column("respiration", sa.Integer(), nullable=True),
        sa.Column("systolic", sa.Integer(), nullable=True),
        sa.Column("diastolic", sa.Integer(), nullable=True),
        sa.Column("spo2", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index("ix_vital_signs_id", "vital_signs", ["id"])
    op.create_index("ix_vital_signs_admission_id", "vital_signs", ["admission_id"])

    op.create_table(
        "nursing_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admission_id", sa.Integer(), sa.ForeignKey("admissions.id"), nullable=False
        ),
        sa.Column("content", sa.String(500), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index("ix_nursing_notes_id", "nursing_notes", ["id"])
    op.create_index("ix_nursing_notes_admission_id", "nursing_notes", ["admission_id"])


def downgrade():
    op.drop_index("ix_nursing_notes_admission_id", table_name="nursing_notes")
    op.drop_index("ix_nursing_notes_id", table_name="nursing_notes")
    op.drop_table("nursing_notes")
    op.drop_index("ix_vital_signs_admission_id", table_name="vital_signs")
    op.drop_index("ix_vital_signs_id", table_name="vital_signs")
    op.drop_table("vital_signs")
