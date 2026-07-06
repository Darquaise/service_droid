"""Add minecraft_status_channel: voice channels mirroring a Minecraft
server's status (online count / restarting / offline) in their name."""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003_minecraft_status_channel"
down_revision: Union[str, None] = "0002_trivia_channel_list_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "minecraft_status_channel",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "channel_id"),
    )


def downgrade() -> None:
    op.drop_table("minecraft_status_channel")
