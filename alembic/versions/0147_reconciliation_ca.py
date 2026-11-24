"""reconciliation CA signature

Revision ID: 0147
Revises: 0146
"""
import sqlalchemy as sa
from alembic import op
revision = "0147"
down_revision = "0146"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("financial_reconciliations") as batch:
        batch.add_column(sa.Column("certificate_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("content_hash", sa.String(64), nullable=False, server_default=""))
        batch.add_column(sa.Column("signature", sa.Text(), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("financial_reconciliations") as batch:
        batch.drop_column("signature")
        batch.drop_column("content_hash")
        batch.drop_column("certificate_id")
