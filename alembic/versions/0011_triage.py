"""add triage tickets (门诊分诊叫号)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "triage_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "registration_id",
            sa.Integer(),
            sa.ForeignKey("registrations.id"),
            nullable=False,
            unique=True,
        ),
        # waiting 候诊 / called 已叫号 / passed 已过号 / done 已完成
        sa.Column("status", sa.String(20), nullable=False, server_default="waiting"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("called_at", sa.DateTime(), nullable=True),
        sa.Column("passed_at", sa.DateTime(), nullable=True),
        sa.Column("done_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_triage_tickets_id", "triage_tickets", ["id"])
    op.create_index(
        "ix_triage_tickets_registration_id", "triage_tickets", ["registration_id"], unique=True
    )


def downgrade():
    op.drop_index("ix_triage_tickets_registration_id", table_name="triage_tickets")
    op.drop_index("ix_triage_tickets_id", table_name="triage_tickets")
    op.drop_table("triage_tickets")
