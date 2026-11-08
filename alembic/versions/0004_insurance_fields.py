"""insurance fields: drugs.insurance_ratio, prescription_items.insurance_warning, payments.insurance_amount

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drugs") as batch_op:
        batch_op.add_column(
            sa.Column("insurance_ratio", sa.Float(), nullable=False, server_default="0.7")
        )
    with op.batch_alter_table("prescription_items") as batch_op:
        batch_op.add_column(
            sa.Column("insurance_warning", sa.String(200), nullable=True)
        )
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(
            sa.Column("insurance_amount", sa.Float(), nullable=False, server_default="0")
        )


def downgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("insurance_amount")
    with op.batch_alter_table("prescription_items") as batch_op:
        batch_op.drop_column("insurance_warning")
    with op.batch_alter_table("drugs") as batch_op:
        batch_op.drop_column("insurance_ratio")
