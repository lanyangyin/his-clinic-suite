"""pacs priority

Revision ID: 0116
Revises: 0115
"""
import sqlalchemy as sa
from alembic import op
revision = "0116"
down_revision = "0115"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.add_column(sa.Column("priority", sa.String(10), nullable=False, server_default="routine"))

def downgrade():
    with op.batch_alter_table("imaging_requests") as batch:
        batch.drop_column("priority")
