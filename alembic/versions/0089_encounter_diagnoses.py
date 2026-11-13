"""multiple encounter diagnoses

Revision ID: 0089
Revises: 0088
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "encounter_diagnoses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id",
            sa.Integer(),
            sa.ForeignKey("encounters.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("diagnosis_code", sa.String(20), nullable=False, server_default=""),
        sa.Column("diagnosis", sa.String(200), nullable=False),
        sa.Column("diagnosis_type", sa.String(20), nullable=False, server_default="primary"),
        sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute(
        """
        INSERT INTO encounter_diagnoses
            (encounter_id, diagnosis_code, diagnosis, diagnosis_type, sort_no, note, created_at)
        SELECT id, diagnosis_code, diagnosis, 'primary', 0, '', created_at
        FROM encounters
        WHERE diagnosis IS NOT NULL AND diagnosis != ''
        """
    )


def downgrade():
    op.drop_table("encounter_diagnoses")
