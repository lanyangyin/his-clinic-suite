"""nursing checker signature

Revision ID: 0149
Revises: 0148
"""
import sqlalchemy as sa
from alembic import op
revision = "0149"
down_revision = "0148"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("nursing_preparations") as batch:
        batch.add_column(sa.Column("checker_signature", sa.String(64), nullable=False, server_default=""))
        batch.add_column(sa.Column("checker_signed_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("nursing_preparations") as batch:
        batch.drop_column("checker_signed_at")
        batch.drop_column("checker_signature")
