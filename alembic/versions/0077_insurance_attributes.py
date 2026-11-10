"""insurance attributes for local catalogs and inbound snapshots

Revision ID: 0077
Revises: 0076
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("material_items") as batch:
        batch.add_column(
            sa.Column("insurance_name", sa.String(100), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "insurance_category",
                sa.String(20),
                nullable=False,
                server_default="未对码",
            )
        )
        batch.add_column(
            sa.Column(
                "insurance_match_status",
                sa.String(20),
                nullable=False,
                server_default="unmatched",
            )
        )

    with op.batch_alter_table("charge_items") as batch:
        batch.add_column(
            sa.Column("insurance_code", sa.String(60), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("insurance_name", sa.String(100), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "insurance_category",
                sa.String(20),
                nullable=False,
                server_default="未对码",
            )
        )
        batch.add_column(
            sa.Column(
                "insurance_match_status",
                sa.String(20),
                nullable=False,
                server_default="unmatched",
            )
        )
        batch.add_column(
            sa.Column("unit", sa.String(20), nullable=False, server_default="次")
        )
        batch.add_column(
            sa.Column(
                "reimbursement_note", sa.String(200), nullable=False, server_default=""
            )
        )

    with op.batch_alter_table("inbound_items") as batch:
        batch.add_column(
            sa.Column("insurance_name", sa.String(100), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "insurance_category",
                sa.String(20),
                nullable=False,
                server_default="未对码",
            )
        )
        batch.add_column(
            sa.Column(
                "insurance_match_status",
                sa.String(20),
                nullable=False,
                server_default="unmatched",
            )
        )
        batch.add_column(
            sa.Column("dosage_form", sa.String(30), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("approval_no", sa.String(60), nullable=False, server_default="")
        )

    with op.batch_alter_table("dict_entries") as batch:
        batch.add_column(
            sa.Column("category", sa.String(50), nullable=False, server_default="")
        )
    op.execute(
        "UPDATE dict_entries SET category = '诊断' "
        "WHERE dict_type = 'diagnosis_icd10' AND category = ''"
    )


def downgrade():
    with op.batch_alter_table("dict_entries") as batch:
        batch.drop_column("category")
    with op.batch_alter_table("inbound_items") as batch:
        batch.drop_column("approval_no")
        batch.drop_column("dosage_form")
        batch.drop_column("insurance_match_status")
        batch.drop_column("insurance_category")
        batch.drop_column("insurance_name")
    with op.batch_alter_table("charge_items") as batch:
        batch.drop_column("reimbursement_note")
        batch.drop_column("unit")
        batch.drop_column("insurance_match_status")
        batch.drop_column("insurance_category")
        batch.drop_column("insurance_name")
        batch.drop_column("insurance_code")
    with op.batch_alter_table("material_items") as batch:
        batch.drop_column("insurance_match_status")
        batch.drop_column("insurance_category")
        batch.drop_column("insurance_name")
