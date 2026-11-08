"""drug trace codes + insurance inventory uploads

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drug_trace_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trace_code", sa.String(64), nullable=False),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("batch_no", sa.String(30), nullable=False, server_default=""),
        # 当前所在库房：总库 / 药房
        sa.Column("warehouse", sa.String(30), nullable=False, server_default="总库"),
        # in_stock 在库 / used 已使用 / returned 已退回 / void 作废
        sa.Column("status", sa.String(20), nullable=False, server_default="in_stock"),
        sa.Column("ref_type", sa.String(20), nullable=False, server_default=""),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("encounter_id", sa.Integer(), nullable=True),
        sa.Column("scanned_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("scanned_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.UniqueConstraint("trace_code"),
    )
    op.create_index("ix_drug_trace_codes_id", "drug_trace_codes", ["id"])
    op.create_index("ix_drug_trace_codes_trace_code", "drug_trace_codes", ["trace_code"])
    op.create_index("ix_drug_trace_codes_drug_id", "drug_trace_codes", ["drug_id"])

    op.create_table(
        "insurance_inventory_uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upload_no", sa.String(30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        # submitted 已提交 / success 成功 / failed 失败
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("payload", sa.Text(), nullable=False, server_default=""),
        sa.Column("response", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("upload_no"),
    )
    op.create_index(
        "ix_insurance_inventory_uploads_id", "insurance_inventory_uploads", ["id"]
    )


def downgrade():
    op.drop_index(
        "ix_insurance_inventory_uploads_id", table_name="insurance_inventory_uploads"
    )
    op.drop_table("insurance_inventory_uploads")
    op.drop_index("ix_drug_trace_codes_drug_id", table_name="drug_trace_codes")
    op.drop_index("ix_drug_trace_codes_trace_code", table_name="drug_trace_codes")
    op.drop_index("ix_drug_trace_codes_id", table_name="drug_trace_codes")
    op.drop_table("drug_trace_codes")
