"""tcm stock

Revision ID: 0126
Revises: 0125
"""
import sqlalchemy as sa
from alembic import op
revision = "0126"
down_revision = "0125"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("tcm_herbs") as batch:
        batch.add_column(sa.Column("stock_g", sa.Float(), nullable=True))

def downgrade():
    with op.batch_alter_table("tcm_herbs") as batch:
        batch.drop_column("stock_g")
