"""tcm stock batches

Revision ID: 0127
Revises: 0126
"""
import sqlalchemy as sa
from alembic import op
revision = "0127"
down_revision = "0126"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tcm_stock_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("herb_id", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.String(50), nullable=False),
        sa.Column("quantity_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expiry", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("herb_id", "batch_no", name="uq_tcm_herb_batch"),
    )
    op.create_index("ix_tcm_stock_batches_herb_id", "tcm_stock_batches", ["herb_id"])

def downgrade():
    op.drop_index("ix_tcm_stock_batches_herb_id", table_name="tcm_stock_batches")
    op.drop_table("tcm_stock_batches")
