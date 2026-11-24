"""seed notification templates

Revision ID: 0138
Revises: 0137
"""
import sqlalchemy as sa
from alembic import op
revision = "0138"
down_revision = "0137"
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
        {"code": "approval_pending", "title": "待审批：{title}", "body": "{applicant} 提交，当前步骤 {step}。", "channel": "internal", "active": True, "created_at": __import__("datetime").datetime.now()},
        {"code": "approval_transfer", "title": "转交审批：{title}", "body": "{actor} 转交给 {target}。{note}", "channel": "internal", "active": True, "created_at": __import__("datetime").datetime.now()},
        {"code": "approval_escalate", "title": "审批超时升级：{title}", "body": "已超过审批时限，升级至院长处理。", "channel": "internal", "active": True, "created_at": __import__("datetime").datetime.now()},
    ])

def downgrade():
    op.execute("DELETE FROM notification_templates WHERE code IN ('approval_pending','approval_transfer','approval_escalate')")
