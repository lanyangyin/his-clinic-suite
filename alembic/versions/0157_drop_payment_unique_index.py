"""删除历史 payments.encounter_id 唯一索引，允许全额退费后重新收费。

Revision ID: 0157
Revises: 0156
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0157"
down_revision: Union[str, None] = "0156"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 旧版本遗留的 UNIQUE INDEX；模型现使用 uq_payments_active_encounter 部分唯一索引。
    op.execute("DROP INDEX IF EXISTS ix_payments_encounter_id")


def downgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_encounter_id "
        "ON payments (encounter_id)"
    )
