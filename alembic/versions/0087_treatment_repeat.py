"""treatment case repeat/follow-up

Revision ID: 0087
Revises: 0086
Create Date: 2026-11-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "treatment_room_cases",
        sa.Column("visit_type", sa.String(20), nullable=False, server_default="initial"),
    )
    op.add_column(
        "treatment_room_cases",
        sa.Column("repeat_of_case_id", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("treatment_room_cases", "repeat_of_case_id")
    op.drop_column("treatment_room_cases", "visit_type")
