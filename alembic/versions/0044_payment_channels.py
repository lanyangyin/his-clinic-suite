"""payment channels + payment channel fields

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_channel_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("display_name", sa.String(50), nullable=False, server_default=""),
        # 以下由实际接入时填写，默认留空（空=模拟支付）
        sa.Column("gateway_url", sa.String(200), nullable=False, server_default=""),
        sa.Column("merchant_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("app_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("api_secret", sa.String(128), nullable=False, server_default=""),
        sa.Column("terminal_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("cert_path", sa.String(200), nullable=False, server_default=""),
        sa.Column("remark", sa.String(200), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(50), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("channel"),
    )
    op.create_index("ix_payment_channel_configs_id", "payment_channel_configs", ["id"])

    with op.batch_alter_table("payments") as batch:
        batch.add_column(
            sa.Column("channel", sa.String(20), nullable=False, server_default="cash")
        )
        batch.add_column(
            sa.Column("channel_trade_no", sa.String(64), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "channel_status", sa.String(20), nullable=False, server_default="success"
            )
        )


def downgrade():
    with op.batch_alter_table("payments") as batch:
        batch.drop_column("channel_status")
        batch.drop_column("channel_trade_no")
        batch.drop_column("channel")
    op.drop_index("ix_payment_channel_configs_id", table_name="payment_channel_configs")
    op.drop_table("payment_channel_configs")
