"""seed approval result template

Revision ID: 0139
Revises: 0138
"""
import sqlalchemy as sa
from alembic import op
revision = "0139"
down_revision = "0138"
branch_labels = None
depends_on = None

def upgrade():
    table = sa.table(
        "notification_templates",
        sa.column("code", sa.String), sa.column("title", sa.String),
        sa.column("body", sa.Text), sa.column("channel", sa.String),
        sa.column("active", sa.Boolean), sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(table, [
        {"code": "approval_result", "title": "审批结果：{title}", "body": "{result}：{note}", "channel": "internal", "active": True, "created_at": __import__("datetime").datetime.now()},
    ])

def downgrade():
    op.execute("DELETE FROM notification_templates WHERE code = 'approval_result'")
