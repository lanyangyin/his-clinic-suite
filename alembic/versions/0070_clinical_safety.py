"""clinical safety: allergy override and triage vitals

Revision ID: 0070
Revises: 0069
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("prescription_items") as batch:
        batch.add_column(sa.Column("allergy_warning", sa.String(300), nullable=True))
        batch.add_column(
            sa.Column("allergy_override_reason", sa.String(300), nullable=True)
        )
        batch.add_column(
            sa.Column("allergy_override_by", sa.String(50), nullable=True)
        )

    with op.batch_alter_table("triage_tickets") as batch:
        batch.add_column(
            sa.Column(
                "triage_level", sa.Integer(), nullable=False, server_default="4"
            )
        )
        batch.add_column(
            sa.Column(
                "chief_complaint", sa.String(200), nullable=False, server_default=""
            )
        )
        batch.add_column(sa.Column("temperature", sa.Float(), nullable=True))
        batch.add_column(sa.Column("pulse", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("respiration", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("systolic", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("diastolic", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("spo2", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("pain_score", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "isolation", sa.Boolean(), nullable=False, server_default="0"
            )
        )
        batch.add_column(
            sa.Column("assessed_by", sa.String(50), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("assessed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("triage_tickets") as batch:
        batch.drop_column("assessed_at")
        batch.drop_column("assessed_by")
        batch.drop_column("isolation")
        batch.drop_column("pain_score")
        batch.drop_column("spo2")
        batch.drop_column("diastolic")
        batch.drop_column("systolic")
        batch.drop_column("respiration")
        batch.drop_column("pulse")
        batch.drop_column("temperature")
        batch.drop_column("chief_complaint")
        batch.drop_column("triage_level")

    with op.batch_alter_table("prescription_items") as batch:
        batch.drop_column("allergy_override_by")
        batch.drop_column("allergy_override_reason")
        batch.drop_column("allergy_warning")
