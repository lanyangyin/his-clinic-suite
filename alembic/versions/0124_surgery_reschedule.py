"""surgery reschedule audit

Revision ID: 0124
Revises: 0123
"""
import sqlalchemy as sa
from alembic import op
revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("surgery_cases") as batch:
        batch.add_column(sa.Column("rescheduled_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("rescheduled_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("reschedule_reason", sa.String(200), nullable=False, server_default=""))

def downgrade():
    with op.batch_alter_table("surgery_cases") as batch:
        batch.drop_column("reschedule_reason")
        batch.drop_column("rescheduled_by")
        batch.drop_column("rescheduled_at")
