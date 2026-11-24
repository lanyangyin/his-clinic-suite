"""pacs report measurements

Revision ID: 0129
Revises: 0128
"""
import sqlalchemy as sa
from alembic import op
revision = "0129"
down_revision = "0128"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.add_column(sa.Column("measurements", sa.String(500), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.drop_column("measurements")
