"""institution settings

Revision ID: 0153
Revises: 0152
"""
import sqlalchemy as sa
from alembic import op
revision = "0153"
down_revision = "0152"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "institution_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("clinic_address", sa.String(200), nullable=False, server_default=""),
        sa.Column("clinic_phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("insurance_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("national_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("national_token", sa.String(500), nullable=False, server_default=""),
        sa.Column("national_org_code", sa.String(100), nullable=False, server_default=""),
        sa.Column("national_region_code", sa.String(100), nullable=False, server_default=""),
        sa.Column("national_operator", sa.String(50), nullable=False, server_default="HIS"),
        sa.Column("national_mock", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table("institution_settings")
