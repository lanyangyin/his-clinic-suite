"""add antibiotic level to drugs

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drugs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "antibiotic_level", sa.Integer(), nullable=False, server_default="0"
            )
        )


def downgrade():
    with op.batch_alter_table("drugs") as batch_op:
        batch_op.drop_column("antibiotic_level")
