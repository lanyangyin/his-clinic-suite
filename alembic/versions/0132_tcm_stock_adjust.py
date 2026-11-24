"""tcm stock adjustments

Revision ID: 0132
Revises: 0131
"""
import sqlalchemy as sa
from alembic import op
revision = "0132"
down_revision = "0131"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tcm_stock_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("delta_g", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("operator", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tcm_stock_adjustments_batch_id", "tcm_stock_adjustments", ["batch_id"])

def downgrade():
    op.drop_index("ix_tcm_stock_adjustments_batch_id", table_name="tcm_stock_adjustments")
    op.drop_table("tcm_stock_adjustments")
