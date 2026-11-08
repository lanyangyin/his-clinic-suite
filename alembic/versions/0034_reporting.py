"""add timestamps for reporting

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("encounters") as batch:
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
    with op.batch_alter_table("prescription_items") as batch:
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )


def downgrade():
    with op.batch_alter_table("prescription_items") as batch:
        batch.drop_column("created_at")
    with op.batch_alter_table("encounters") as batch:
        batch.drop_column("created_at")
