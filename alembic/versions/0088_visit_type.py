"""visit type for registration and encounter

Revision ID: 0088
Revises: 0087
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "registrations",
        sa.Column("visit_type", sa.String(20), nullable=False, server_default="initial"),
    )
    op.add_column(
        "registrations",
        sa.Column("original_registration_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "encounters",
        sa.Column("visit_type", sa.String(20), nullable=False, server_default="initial"),
    )
    op.add_column(
        "encounters",
        sa.Column("original_encounter_id", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("encounters", "original_encounter_id")
    op.drop_column("encounters", "visit_type")
    op.drop_column("registrations", "original_registration_id")
    op.drop_column("registrations", "visit_type")
