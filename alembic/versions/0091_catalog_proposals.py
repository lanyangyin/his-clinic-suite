"""catalog proposals

Revision ID: 0091
Revises: 0090
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "catalog_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("spec", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("review_note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_object_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_catalog_proposals_kind", "catalog_proposals", ["kind"])
    op.create_index("ix_catalog_proposals_status", "catalog_proposals", ["status"])


def downgrade():
    op.drop_index("ix_catalog_proposals_status", table_name="catalog_proposals")
    op.drop_index("ix_catalog_proposals_kind", table_name="catalog_proposals")
    op.drop_table("catalog_proposals")
