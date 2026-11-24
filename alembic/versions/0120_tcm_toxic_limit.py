"""tcm toxic max dose

Revision ID: 0120
Revises: 0119
"""
import sqlalchemy as sa
from alembic import op
revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("tcm_herbs") as batch:
        batch.add_column(sa.Column("max_dose_g", sa.Float(), nullable=False, server_default="0"))

def downgrade():
    with op.batch_alter_table("tcm_herbs") as batch:
        batch.drop_column("max_dose_g")
