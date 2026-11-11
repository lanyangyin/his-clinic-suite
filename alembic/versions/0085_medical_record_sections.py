"""medical record sections

Revision ID: 0085
Revises: 0084
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None

COLUMNS = ("personal_history", "marital_history", "family_history", "auxiliary_exam")


def upgrade():
    with op.batch_alter_table("medical_records") as batch:
        for name in COLUMNS:
            batch.add_column(sa.Column(name, sa.String(1000), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("medical_records") as batch:
        for name in reversed(COLUMNS):
            batch.drop_column(name)
