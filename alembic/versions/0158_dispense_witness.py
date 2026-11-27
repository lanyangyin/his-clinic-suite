"""dispensations 增加第二见证人字段。

Revision ID: 0158
Revises: 0157
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0158"
down_revision: Union[str, None] = "0157"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {row["name"] for row in sa.inspect(bind).get_columns("dispensations")}
    if "witness" not in columns:
        op.add_column(
            "dispensations",
            sa.Column("witness", sa.String(50), nullable=False, server_default=""),
        )


def downgrade() -> None:
    op.drop_column("dispensations", "witness")
