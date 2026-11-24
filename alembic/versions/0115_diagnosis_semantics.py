"""diagnosis stage/phase/certainty

Revision ID: 0115
Revises: 0114
"""
import sqlalchemy as sa
from alembic import op

revision = "0115"
down_revision = "0114"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("encounter_diagnoses") as batch:
        batch.add_column(sa.Column("diagnosis_stage", sa.String(20), nullable=False, server_default="outpatient"))
        batch.add_column(sa.Column("diagnosis_phase", sa.String(20), nullable=False, server_default="initial"))
        batch.add_column(sa.Column("diagnosis_certainty", sa.String(20), nullable=False, server_default="confirmed"))


def downgrade():
    with op.batch_alter_table("encounter_diagnoses") as batch:
        batch.drop_column("diagnosis_certainty")
        batch.drop_column("diagnosis_phase")
        batch.drop_column("diagnosis_stage")
