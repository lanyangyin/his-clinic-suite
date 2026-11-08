"""add dispense status for outpatient returns

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dispensations") as batch:
        batch.add_column(
            sa.Column("status", sa.String(10), nullable=False, server_default="dispensed")
        )
        batch.add_column(sa.Column("returned_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("dispensations") as batch:
        batch.drop_column("returned_at")
        batch.drop_column("status")
