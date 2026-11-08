"""insurance interface config + upload channel

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "insurance_interface_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        # 平台地址、机构编码等由实际部署时填写，默认留空（空=走 Mock）
        sa.Column("base_url", sa.String(200), nullable=False, server_default=""),
        sa.Column("upload_path", sa.String(100), nullable=False, server_default="/api/inventory/upload"),
        sa.Column("org_code", sa.String(50), nullable=False, server_default=""),
        sa.Column("org_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("app_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("app_secret", sa.String(128), nullable=False, server_default=""),
        sa.Column("sign_type", sa.String(20), nullable=False, server_default="NONE"),
        sa.Column("private_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("public_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("timeout", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("remark", sa.String(200), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    with op.batch_alter_table("insurance_inventory_uploads") as batch:
        batch.add_column(
            sa.Column("channel", sa.String(20), nullable=False, server_default="mock")
        )


def downgrade():
    with op.batch_alter_table("insurance_inventory_uploads") as batch:
        batch.drop_column("channel")
    op.drop_table("insurance_interface_config")
