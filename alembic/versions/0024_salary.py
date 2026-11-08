"""add salary requests (HRP)

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "salary_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False
        ),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("base_amount", sa.Float(), nullable=False),
        sa.Column("bonus_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Float(), nullable=False),
        # pending 待审批 / approved 已批准 / rejected 已驳回
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("requested_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("review_note", sa.String(200), nullable=False, server_default=""),
        sa.UniqueConstraint("employee_id", "month", name="uq_salary_employee_month"),
    )
    op.create_index("ix_salary_requests_id", "salary_requests", ["id"])
    op.create_index(
        "ix_salary_requests_employee_id", "salary_requests", ["employee_id"]
    )


def downgrade():
    op.drop_index("ix_salary_requests_employee_id", table_name="salary_requests")
    op.drop_index("ix_salary_requests_id", table_name="salary_requests")
    op.drop_table("salary_requests")
