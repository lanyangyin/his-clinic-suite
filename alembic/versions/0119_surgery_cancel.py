"""surgery cancel audit

Revision ID: 0119
Revises: 0118
"""
import sqlalchemy as sa
from alembic import op
revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("surgery_cases") as batch:
        batch.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("cancelled_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("cancel_reason", sa.String(200), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("surgery_cases") as batch:
        batch.drop_column("cancel_reason")
        batch.drop_column("cancelled_by")
        batch.drop_column("cancelled_at")
