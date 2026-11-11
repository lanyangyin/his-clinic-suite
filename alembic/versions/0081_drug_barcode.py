"""drug barcode

Revision ID: 0081
Revises: 0080
Create Date: 2026-11-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drugs") as batch:
        batch.add_column(
            sa.Column("barcode", sa.String(50), nullable=False, server_default="")
        )


def downgrade():
    with op.batch_alter_table("drugs") as batch:
        batch.drop_column("barcode")
