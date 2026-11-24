"""nursing started/completed by

Revision ID: 0118
Revises: 0117
"""
import sqlalchemy as sa
from alembic import op
revision = "0118"
down_revision = "0117"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("nursing_orders") as batch:
        batch.add_column(sa.Column("started_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("completed_by", sa.String(50), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("nursing_orders") as batch:
        batch.drop_column("completed_by")
        batch.drop_column("started_by")
