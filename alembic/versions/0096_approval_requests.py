"""generic approval requests and steps

Revision ID: 0096
Revises: 0095
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("biz_type", sa.String(length=30), nullable=False),
        sa.Column("biz_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_approval_requests_biz_type", "approval_requests", ["biz_type"])
    op.create_index("ix_approval_requests_biz_id", "approval_requests", ["biz_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_table(
        "approval_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("approval_requests.id"), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("role_required", sa.String(length=20), nullable=False, server_default="pharmacist"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("approver", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("acted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_approval_steps_request_id", "approval_steps", ["request_id"])


def downgrade():
    op.drop_index("ix_approval_steps_request_id", table_name="approval_steps")
    op.drop_table("approval_steps")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_biz_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_biz_type", table_name="approval_requests")
    op.drop_table("approval_requests")
