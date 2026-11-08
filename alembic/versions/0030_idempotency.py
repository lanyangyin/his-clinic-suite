"""add idempotency keys

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("endpoint", sa.String(200), nullable=False),
        # processing 处理中 / done 已完成
        sa.Column("status", sa.String(10), nullable=False, server_default="processing"),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("key", "endpoint", name="uq_idempotency_key_endpoint"),
    )
    op.create_index("ix_idempotency_keys_id", "idempotency_keys", ["id"])


def downgrade():
    op.drop_index("ix_idempotency_keys_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
