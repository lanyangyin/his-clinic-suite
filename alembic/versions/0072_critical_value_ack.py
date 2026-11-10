"""critical value doctor acknowledgement

Revision ID: 0072
Revises: 0071
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lab_requests") as batch:
        batch.add_column(sa.Column("critical_ack_by", sa.String(50), nullable=True))
        batch.add_column(sa.Column("critical_ack_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("critical_ack_note", sa.String(200), nullable=True))


def downgrade():
    with op.batch_alter_table("lab_requests") as batch:
        batch.drop_column("critical_ack_note")
        batch.drop_column("critical_ack_at")
        batch.drop_column("critical_ack_by")
