"""pacs item insurance ratio

Revision ID: 0117
Revises: 0116
"""
import sqlalchemy as sa
from alembic import op
revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("imaging_items") as batch:
        batch.add_column(sa.Column("insurance_ratio", sa.Float(), nullable=False, server_default="0.7"))

def downgrade():
    with op.batch_alter_table("imaging_items") as batch:
        batch.drop_column("insurance_ratio")
