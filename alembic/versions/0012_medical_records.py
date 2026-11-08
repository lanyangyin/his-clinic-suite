"""add medical records (门诊结构化病历)

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "medical_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id",
            sa.Integer(),
            sa.ForeignKey("encounters.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("chief_complaint", sa.String(200), nullable=False),
        sa.Column("present_illness", sa.String(1000), nullable=False, server_default=""),
        sa.Column("past_history", sa.String(1000), nullable=False, server_default=""),
        sa.Column("physical_exam", sa.String(1000), nullable=False, server_default=""),
        sa.Column("treatment_advice", sa.String(500), nullable=False, server_default=""),
        sa.Column("written_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_medical_records_id", "medical_records", ["id"])
    op.create_index(
        "ix_medical_records_encounter_id", "medical_records", ["encounter_id"], unique=True
    )


def downgrade():
    op.drop_index("ix_medical_records_encounter_id", table_name="medical_records")
    op.drop_index("ix_medical_records_id", table_name="medical_records")
    op.drop_table("medical_records")
