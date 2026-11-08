"""add CA certificates and seals

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ca_certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("serial_no", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("private_key", sa.String(64), nullable=False),
        sa.Column("public_key", sa.String(128), nullable=False),
        # valid 有效 / revoked 已吊销
        sa.Column("status", sa.String(20), nullable=False, server_default="valid"),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("serial_no"),
    )
    op.create_index("ix_ca_certificates_id", "ca_certificates", ["id"])

    op.create_table(
        "ca_seals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "certificate_id", sa.Integer(), sa.ForeignKey("ca_certificates.id"), nullable=False
        ),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(512), nullable=False),
        sa.Column("sealed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "certificate_id", "target_type", "target_id", name="uq_ca_seal"
        ),
    )
    op.create_index("ix_ca_seals_id", "ca_seals", ["id"])
    op.create_index("ix_ca_seals_target_id", "ca_seals", ["target_id"])


def downgrade():
    op.drop_index("ix_ca_seals_target_id", table_name="ca_seals")
    op.drop_index("ix_ca_seals_id", table_name="ca_seals")
    op.drop_table("ca_seals")
    op.drop_index("ix_ca_certificates_id", table_name="ca_certificates")
    op.drop_table("ca_certificates")
