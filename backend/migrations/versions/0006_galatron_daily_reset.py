"""Galatron: the cooldown is a fixed daily reset at 00:00 UTC, so the configurable
cooldown (and its timeline) is gone.

Downgrade recreates the table and gives every guild the old 24 h default again; custom
values set before the upgrade are not recoverable.
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006_galatron_daily_reset"
down_revision: Union[str, None] = "0005_galatron_register"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("galatron_cooldown")


def downgrade() -> None:
    op.create_table(
        "galatron_cooldown",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cooldown_s", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "valid_from"),
    )
    op.execute(
        """
        INSERT INTO galatron_cooldown (guild_id, valid_from, cooldown_s)
        SELECT guild_id, TIMESTAMPTZ 'epoch', 86400 FROM guild
        """
    )
