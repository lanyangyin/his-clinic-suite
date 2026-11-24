"""discharge medication dispense

Revision ID: 0141
Revises: 0140
"""
import sqlalchemy as sa
from alembic import op
revision = "0141"
down_revision = "0140"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("discharge_medications") as batch:
        batch.add_column(sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("amount", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="pending"))
        batch.add_column(sa.Column("dispensed_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("dispensed_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("discharge_medications") as batch:
        batch.drop_column("dispensed_at")
        batch.drop_column("dispensed_by")
        batch.drop_column("status")
        batch.drop_column("amount")
        batch.drop_column("unit_price")
