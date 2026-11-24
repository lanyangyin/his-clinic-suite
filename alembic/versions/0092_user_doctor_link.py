"""user doctor link

Revision ID: 0092
Revises: 0091
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("doctor_id", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("users", "doctor_id")
