"""add employees table (HRP)

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_no", sa.String(30), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column(
            "department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("email", sa.String(100), nullable=False, server_default=""),
        sa.Column("hired_at", sa.Date(), nullable=False),
        # active 在职 / resigned 已离职
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("resigned_at", sa.Date(), nullable=True),
        sa.UniqueConstraint("employee_no"),
    )
    op.create_index("ix_employees_id", "employees", ["id"])


def downgrade():
    op.drop_index("ix_employees_id", table_name="employees")
    op.drop_table("employees")
