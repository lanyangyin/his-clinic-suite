"""high alert drugs and nursing double check

Revision ID: 0073
Revises: 0072
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drugs") as batch:
        batch.add_column(
            sa.Column(
                "high_alert", sa.Boolean(), nullable=False, server_default="0"
            )
        )
    with op.batch_alter_table("nursing_orders") as batch:
        batch.add_column(
            sa.Column(
                "high_alert", sa.Boolean(), nullable=False, server_default="0"
            )
        )


def downgrade():
    with op.batch_alter_table("nursing_orders") as batch:
        batch.drop_column("high_alert")
    with op.batch_alter_table("drugs") as batch:
        batch.drop_column("high_alert")
