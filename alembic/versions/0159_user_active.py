"""users 增加 is_active，支持离职/停用账号。"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0159"
down_revision: Union[str, None] = "0158"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {row["name"] for row in sa.inspect(bind).get_columns("users")}
    if "is_active" not in columns:
        op.add_column(
            "users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1")
        )


def downgrade() -> None:
    op.drop_column("users", "is_active")
