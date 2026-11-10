"""patient P0 profile

Revision ID: 0069
Revises: 0068
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("patients") as batch:
        batch.alter_column(
            "id_number",
            existing_type=sa.String(18),
            type_=sa.String(30),
            nullable=True,
        )
        batch.add_column(sa.Column("patient_no", sa.String(20), nullable=True))
        batch.add_column(
            sa.Column("id_type", sa.String(20), nullable=False, server_default="id_card")
        )
        batch.add_column(
            sa.Column("gender", sa.String(10), nullable=False, server_default="unknown")
        )
        batch.add_column(sa.Column("birth_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("address", sa.String(200), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "emergency_contact_name",
                sa.String(50),
                nullable=False,
                server_default="",
            )
        )
        batch.add_column(
            sa.Column(
                "emergency_contact_relation",
                sa.String(20),
                nullable=False,
                server_default="",
            )
        )
        batch.add_column(
            sa.Column(
                "emergency_contact_phone",
                sa.String(20),
                nullable=False,
                server_default="",
            )
        )
        batch.add_column(
            sa.Column(
                "insurance_type",
                sa.String(20),
                nullable=False,
                server_default="self_pay",
            )
        )
        batch.add_column(
            sa.Column(
                "allergy_status",
                sa.String(20),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(
            sa.Column(
                "allergy_detail", sa.String(200), nullable=False, server_default=""
            )
        )
        batch.add_column(sa.Column("privacy_consent_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(20), nullable=False, server_default="normal")
        )
        batch.add_column(sa.Column("merged_into_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("created_by", sa.String(50), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("updated_by", sa.String(50), nullable=False, server_default="")
        )

    op.execute(
        "UPDATE patients SET patient_no = 'P' || substr('00000000' || id, -8) "
        "WHERE patient_no IS NULL"
    )
    op.create_index(
        "ux_patients_patient_no", "patients", ["patient_no"], unique=True
    )


def downgrade():
    op.drop_index("ux_patients_patient_no", table_name="patients")
    with op.batch_alter_table("patients") as batch:
        batch.drop_column("updated_by")
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
        batch.drop_column("created_by")
        batch.drop_column("merged_into_id")
        batch.drop_column("status")
        batch.drop_column("privacy_consent_at")
        batch.drop_column("allergy_detail")
        batch.drop_column("allergy_status")
        batch.drop_column("insurance_type")
        batch.drop_column("emergency_contact_phone")
        batch.drop_column("emergency_contact_relation")
        batch.drop_column("emergency_contact_name")
        batch.drop_column("address")
        batch.drop_column("birth_date")
        batch.drop_column("gender")
        batch.drop_column("id_type")
        batch.drop_column("patient_no")
        batch.alter_column(
            "id_number",
            existing_type=sa.String(30),
            type_=sa.String(18),
            nullable=False,
        )
