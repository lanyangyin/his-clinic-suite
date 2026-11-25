"""insurance national transaction fields

Revision ID: 0151
Revises: 0150
"""
import sqlalchemy as sa
from alembic import op
revision = "0151"
down_revision = "0150"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("insurance_transactions") as batch:
        batch.add_column(sa.Column("infno", sa.String(10), nullable=False, server_default=""))
        batch.add_column(sa.Column("trade_no", sa.String(64), nullable=False, server_default=""))
        batch.add_column(sa.Column("request_json", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("response_json", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default=""))
        batch.add_column(sa.Column("mode", sa.String(20), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("insurance_transactions") as batch:
        batch.drop_column("mode")
        batch.drop_column("status")
        batch.drop_column("response_json")
        batch.drop_column("request_json")
        batch.drop_column("trade_no")
        batch.drop_column("infno")
