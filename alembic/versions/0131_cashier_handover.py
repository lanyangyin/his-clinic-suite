"""cashier handover

Revision ID: 0131
Revises: 0130
"""
import sqlalchemy as sa
from alembic import op
revision = "0131"
down_revision = "0130"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("cashier_shifts") as batch:
        batch.add_column(sa.Column("handover_to", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("handover_signature", sa.String(50), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("cashier_shifts") as batch:
        batch.drop_column("handover_signature")
        batch.drop_column("handover_to")
