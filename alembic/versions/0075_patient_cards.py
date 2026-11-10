"""patient NFC cards

Revision ID: 0075
Revises: 0074
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "patient_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id"),
            nullable=False,
        ),
        sa.Column("card_uid", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="active"
        ),
        sa.Column(
            "issued_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "issued_by", sa.String(50), nullable=False, server_default=""
        ),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_patient_cards_id", "patient_cards", ["id"])
    op.create_index(
        "ix_patient_cards_patient_id", "patient_cards", ["patient_id"]
    )
    op.create_index("ix_patient_cards_card_uid", "patient_cards", ["card_uid"])


def downgrade():
    op.drop_table("patient_cards")
