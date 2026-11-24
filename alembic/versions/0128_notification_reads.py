"""per-user notification reads

Revision ID: 0128
Revises: 0127
"""
import sqlalchemy as sa
from alembic import op
revision = "0128"
down_revision = "0127"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "notification_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notification_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("notification_id", "username", name="uq_notification_user_read"),
    )
    op.create_index("ix_notification_reads_notification_id", "notification_reads", ["notification_id"])
    op.create_index("ix_notification_reads_username", "notification_reads", ["username"])

def downgrade():
    op.drop_index("ix_notification_reads_username", table_name="notification_reads")
    op.drop_index("ix_notification_reads_notification_id", table_name="notification_reads")
    op.drop_table("notification_reads")
