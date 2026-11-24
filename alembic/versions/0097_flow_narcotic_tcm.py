"""approval flow config, narcotic ledger, unified TCM header

Revision ID: 0097
Revises: 0096
Create Date: 2026-11-22
"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "approval_flow_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("biz_type", sa.String(length=30), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("role_required", sa.String(length=20), nullable=False),
        sa.Column("due_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_approval_flow_steps_biz_type", "approval_flow_steps", ["biz_type"])
    op.add_column("approval_requests", sa.Column("applicant", sa.String(length=50), nullable=False, server_default=""))
    op.add_column("approval_requests", sa.Column("due_at", sa.DateTime(), nullable=True))
    op.add_column("approval_steps", sa.Column("assignee", sa.String(length=50), nullable=False, server_default=""))
    op.add_column("approval_steps", sa.Column("due_at", sa.DateTime(), nullable=True))

    op.add_column("tcm_prescriptions", sa.Column("prescription_id", sa.Integer(), nullable=True))
    op.create_index("ix_tcm_prescriptions_prescription_id", "tcm_prescriptions", ["prescription_id"])

    op.create_table(
        "narcotic_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("drug_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id"), nullable=True),
        sa.Column("dispense_id", sa.Integer(), sa.ForeignKey("dispensations.id"), nullable=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("batch_no", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("operator", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("witness", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_narcotic_ledger_drug_id", "narcotic_ledger", ["drug_id"])
    op.create_index("ix_narcotic_ledger_prescription_id", "narcotic_ledger", ["prescription_id"])
    op.create_index("ix_narcotic_ledger_dispense_id", "narcotic_ledger", ["dispense_id"])
    op.create_index("ix_narcotic_ledger_patient_id", "narcotic_ledger", ["patient_id"])
    op.create_index("ix_narcotic_ledger_action", "narcotic_ledger", ["action"])

    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, encounter_id, doctor, status, created_at FROM tcm_prescriptions "
        "WHERE prescription_id IS NULL"
    )).fetchall()
    for row in rows:
        mapped = "approved" if row.status in ("reviewed", "dispensed", "decocting", "completed") else "pending_review"
        if row.status == "cancelled":
            mapped = "cancelled"
        no = f"TCMLEGACY{row.id:06d}"
        conn.execute(
            sa.text(
                "INSERT INTO prescriptions "
                "(encounter_id, prescription_no, type, status, prescribed_by, reviewed_by, "
                "review_note, insurance_upload_status, created_at) "
                "VALUES (:e, :no, 'tcm_herb', :status, :doctor, '', '中药处方回填', 'not_ready', :at)"
            ),
            {"e": row.encounter_id, "no": no, "status": mapped, "doctor": row.doctor or "", "at": row.created_at or datetime.now()},
        )
        pid = conn.execute(sa.text("SELECT id FROM prescriptions WHERE prescription_no = :no"), {"no": no}).scalar()
        conn.execute(sa.text("UPDATE tcm_prescriptions SET prescription_id = :pid WHERE id = :id"), {"pid": pid, "id": row.id})


def downgrade():
    op.drop_index("ix_narcotic_ledger_action", table_name="narcotic_ledger")
    op.drop_index("ix_narcotic_ledger_patient_id", table_name="narcotic_ledger")
    op.drop_index("ix_narcotic_ledger_dispense_id", table_name="narcotic_ledger")
    op.drop_index("ix_narcotic_ledger_prescription_id", table_name="narcotic_ledger")
    op.drop_index("ix_narcotic_ledger_drug_id", table_name="narcotic_ledger")
    op.drop_table("narcotic_ledger")
    op.drop_index("ix_tcm_prescriptions_prescription_id", table_name="tcm_prescriptions")
    op.drop_column("tcm_prescriptions", "prescription_id")
    op.drop_column("approval_steps", "due_at")
    op.drop_column("approval_steps", "assignee")
    op.drop_column("approval_requests", "due_at")
    op.drop_column("approval_requests", "applicant")
    op.drop_index("ix_approval_flow_steps_biz_type", table_name="approval_flow_steps")
    op.drop_table("approval_flow_steps")
