"""clinical prescription/dispense/audit refactor

Revision ID: 0093
Revises: 0092
Create Date: 2026-11-22
"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prescriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("prescription_no", sa.String(length=40), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="western"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="approved"),
        sa.Column("prescribed_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("prescription_no"),
    )
    op.create_index("ix_prescriptions_encounter_id", "prescriptions", ["encounter_id"])
    op.create_index("ix_prescriptions_status", "prescriptions", ["status"])
    op.add_column("prescription_items", sa.Column("prescription_id", sa.Integer(), nullable=True))
    op.create_index("ix_prescription_items_prescription_id", "prescription_items", ["prescription_id"])

    op.create_table(
        "dispense_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dispense_id", sa.Integer(), sa.ForeignKey("dispensations.id"), nullable=False),
        sa.Column("prescription_item_id", sa.Integer(), sa.ForeignKey("prescription_items.id"), nullable=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=True),
        sa.Column("drug_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("spec", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("batch_no", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("returned_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_dispense_items_dispense_id", "dispense_items", ["dispense_id"])

    op.create_table(
        "medical_record_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("medical_records.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=20), nullable=False, server_default="update"),
        sa.Column("before_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("after_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_medical_record_versions_record_id", "medical_record_versions", ["record_id"])

    op.create_table(
        "patient_access_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False, server_default="view"),
        sa.Column("path", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("method", sa.String(length=10), nullable=False, server_default="GET"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_patient_access_logs_username", "patient_access_logs", ["username"])
    op.create_index("ix_patient_access_logs_patient_id", "patient_access_logs", ["patient_id"])

    # 兼容旧数据：每个已有处方明细的就诊补一张已批准的处方头
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT encounter_id, MIN(created_at) AS created_at "
        "FROM prescription_items GROUP BY encounter_id"
    )).fetchall()
    for encounter_id, created_at in rows:
        no = f"RXLEGACY{encounter_id:08d}"
        conn.execute(
            sa.text(
                "INSERT INTO prescriptions "
                "(encounter_id, prescription_no, type, status, prescribed_by, reviewed_by, "
                "review_note, created_at) "
                "VALUES (:e, :no, 'western', 'approved', '', '', '历史处方回填', :at)"
            ),
            {"e": encounter_id, "no": no, "at": created_at or datetime.now()},
        )
        pid = conn.execute(
            sa.text("SELECT id FROM prescriptions WHERE prescription_no = :no"),
            {"no": no},
        ).scalar()
        conn.execute(
            sa.text("UPDATE prescription_items SET prescription_id = :pid WHERE encounter_id = :e"),
            {"pid": pid, "e": encounter_id},
        )


def downgrade():
    op.drop_index("ix_patient_access_logs_patient_id", table_name="patient_access_logs")
    op.drop_index("ix_patient_access_logs_username", table_name="patient_access_logs")
    op.drop_table("patient_access_logs")
    op.drop_index("ix_medical_record_versions_record_id", table_name="medical_record_versions")
    op.drop_table("medical_record_versions")
    op.drop_index("ix_dispense_items_dispense_id", table_name="dispense_items")
    op.drop_table("dispense_items")
    op.drop_index("ix_prescription_items_prescription_id", table_name="prescription_items")
    op.drop_column("prescription_items", "prescription_id")
    op.drop_index("ix_prescriptions_status", table_name="prescriptions")
    op.drop_index("ix_prescriptions_encounter_id", table_name="prescriptions")
    op.drop_table("prescriptions")
