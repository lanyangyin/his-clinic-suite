"""discharge medication charge

Revision ID: 0142
Revises: 0141
"""
import sqlalchemy as sa
from alembic import op
revision = "0142"
down_revision = "0141"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("inpatient_charges") as batch:
        batch.alter_column("execution_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("discharge_medication_id", sa.Integer(), nullable=True))
        batch.create_index("ix_inpatient_charges_discharge_medication_id", ["discharge_medication_id"], unique=True)

def downgrade():
    with op.batch_alter_table("inpatient_charges") as batch:
        batch.drop_index("ix_inpatient_charges_discharge_medication_id")
        batch.drop_column("discharge_medication_id")
        batch.alter_column("execution_id", existing_type=sa.Integer(), nullable=False)
