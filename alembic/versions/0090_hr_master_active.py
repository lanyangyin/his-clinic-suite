"""department/doctor soft-delete and user employee link

Revision ID: 0090
Revises: 0089
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("departments", sa.Column("active", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("doctors", sa.Column("active", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("employee_id", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("users", "employee_id")
    op.drop_column("doctors", "active")
    op.drop_column("departments", "active")
