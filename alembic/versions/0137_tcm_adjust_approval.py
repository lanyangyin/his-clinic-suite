"""tcm stock adjustment approval

Revision ID: 0137
Revises: 0136
"""
import sqlalchemy as sa
from alembic import op
revision = "0137"
down_revision = "0136"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("tcm_stock_adjustments") as batch:
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="approved"))
        batch.add_column(sa.Column("approved_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("tcm_stock_adjustments") as batch:
        batch.drop_column("approved_at")
        batch.drop_column("approved_by")
        batch.drop_column("status")
