"""add LIS tables: lab_items, lab_requests

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lab_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_lab_items_id", "lab_items", ["id"])

    op.create_table(
        "lab_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False
        ),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("lab_items.id"), nullable=False),
        # pending 已申请 / reported 已出结果
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("reported_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.String(500), nullable=True),
    )
    op.create_index("ix_lab_requests_id", "lab_requests", ["id"])
    op.create_index("ix_lab_requests_encounter_id", "lab_requests", ["encounter_id"])


def downgrade():
    op.drop_index("ix_lab_requests_encounter_id", table_name="lab_requests")
    op.drop_index("ix_lab_requests_id", table_name="lab_requests")
    op.drop_table("lab_requests")
    op.drop_index("ix_lab_items_id", table_name="lab_items")
    op.drop_table("lab_items")
