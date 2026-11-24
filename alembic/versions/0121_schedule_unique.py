"""doctor schedule unique slot

Revision ID: 0121
Revises: 0120
"""
from alembic import op
revision = "0121"
down_revision = "0120"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("doctor_schedules") as batch:
        batch.create_unique_constraint("uq_doctor_schedule_slot", ["doctor_id", "schedule_date", "period"])

def downgrade():
    with op.batch_alter_table("doctor_schedules") as batch:
        batch.drop_constraint("uq_doctor_schedule_slot", type_="unique")
