"""approval event timeline

Revision ID: 0094
Revises: 0093
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "approval_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("biz_type", sa.String(length=30), nullable=False),
        sa.Column("biz_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.String(length=30), nullable=False, server_default="review"),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_approval_events_biz_type", "approval_events", ["biz_type"])
    op.create_index("ix_approval_events_biz_id", "approval_events", ["biz_id"])


def downgrade():
    op.drop_index("ix_approval_events_biz_id", table_name="approval_events")
    op.drop_index("ix_approval_events_biz_type", table_name="approval_events")
    op.drop_table("approval_events")
