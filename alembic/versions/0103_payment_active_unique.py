"""one active payment per encounter

Revision ID: 0103
Revises: 0102
"""
import sqlalchemy as sa
from alembic import op

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_payments_active_encounter",
        "payments",
        ["encounter_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('paid', 'partially_refunded')"),
    )


def downgrade():
    op.drop_index("uq_payments_active_encounter", table_name="payments")
