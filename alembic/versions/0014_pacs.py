"""add PACS tables: imaging_items, imaging_requests

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "imaging_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("body_part", sa.String(50), nullable=False, server_default=""),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_imaging_items_id", "imaging_items", ["id"])

    op.create_table(
        "imaging_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False
        ),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("imaging_items.id"), nullable=False),
        # 影像号（PACS 检查关联标识）
        sa.Column("accession_no", sa.String(30), nullable=False),
        # pending 已申请 / reported 已出报告
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("reported_at", sa.DateTime(), nullable=True),
        sa.Column("report", sa.String(500), nullable=True),
        sa.Column("image_url", sa.String(200), nullable=False, server_default=""),
        sa.UniqueConstraint("accession_no"),
    )
    op.create_index("ix_imaging_requests_id", "imaging_requests", ["id"])
    op.create_index("ix_imaging_requests_encounter_id", "imaging_requests", ["encounter_id"])


def downgrade():
    op.drop_index("ix_imaging_requests_encounter_id", table_name="imaging_requests")
    op.drop_index("ix_imaging_requests_id", table_name="imaging_requests")
    op.drop_table("imaging_requests")
    op.drop_index("ix_imaging_items_id", table_name="imaging_items")
    op.drop_table("imaging_items")
