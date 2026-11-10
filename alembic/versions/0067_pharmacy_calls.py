"""pharmacy calls and dispense verification

Revision ID: 0067
Revises: 0066
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dispensations") as batch:
        batch.add_column(sa.Column("verified_by", sa.String(50), nullable=False, server_default=""))
        batch.add_column(sa.Column("verified_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("note", sa.String(200), nullable=False, server_default=""))

    op.create_table(
        "pharmacy_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False, unique=True),
        sa.Column("queue_no", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="called"),
        sa.Column("window_no", sa.String(20), nullable=False, server_default=""),
        sa.Column("called_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("called_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_pharmacy_calls_id", "pharmacy_calls", ["id"])
    op.create_index("ix_pharmacy_calls_encounter_id", "pharmacy_calls", ["encounter_id"])


def downgrade():
    op.drop_table("pharmacy_calls")
    with op.batch_alter_table("dispensations") as batch:
        batch.drop_column("note")
        batch.drop_column("verified_at")
        batch.drop_column("verified_by")
