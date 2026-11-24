"""surgery signatures

Revision ID: 0148
Revises: 0147
"""
import sqlalchemy as sa
from alembic import op
revision = "0148"
down_revision = "0147"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("surgery_cases") as batch:
        batch.add_column(sa.Column("signatures_required", sa.Boolean(), nullable=False, server_default="0"))
    op.create_table(
        "surgery_signatures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("case_id", "role", name="uq_surgery_signature_case_role"),
    )
    op.create_index("ix_surgery_signatures_case_id", "surgery_signatures", ["case_id"])

def downgrade():
    op.drop_index("ix_surgery_signatures_case_id", table_name="surgery_signatures")
    op.drop_table("surgery_signatures")
    with op.batch_alter_table("surgery_cases") as batch:
        batch.drop_column("signatures_required")
