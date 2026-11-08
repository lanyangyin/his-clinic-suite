"""add medical record signature fields

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("medical_records") as batch_op:
        batch_op.add_column(sa.Column("signed_by", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("signed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("medical_records") as batch_op:
        batch_op.drop_column("signed_at")
        batch_op.drop_column("signed_by")
