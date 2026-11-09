"""insurance inventory skipped unmatched records

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("insurance_inventory_uploads") as batch:
        batch.add_column(
            sa.Column(
                "skipped_count", sa.Integer(), nullable=False, server_default="0"
            )
        )


def downgrade():
    with op.batch_alter_table("insurance_inventory_uploads") as batch:
        batch.drop_column("skipped_count")
