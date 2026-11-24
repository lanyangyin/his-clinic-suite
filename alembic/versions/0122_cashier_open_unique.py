"""one open cashier shift

Revision ID: 0122
Revises: 0121
"""
import sqlalchemy as sa
from alembic import op
revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None

def upgrade():
    op.create_index(
        "uq_cashier_open_shift", "cashier_shifts", ["cashier"], unique=True,
        sqlite_where=sa.text("status = 'open'"),
    )

def downgrade():
    op.drop_index("uq_cashier_open_shift", table_name="cashier_shifts")
