"""Galatron: one row per attempt instead of a counter, plus cooldown/chance timelines.

``galatron_attempt`` replaces both ``galatron_history`` (a win is an attempt with
``won``) and ``galatron_member`` (totals are a COUNT, the cooldown stamp a MAX).
``galatron_cooldown``/``galatron_chance`` replace the two ``guild`` columns so both
settings stay traceable over time.

The existing wins carry over with their timestamps; the per-member counters cannot
(they never had any) — for the production guild they are re-imported from the
reconstructed channel history. The carried-over cooldown/chance start at the epoch;
the bot pulls that start forward to its guild join on the next boot
(``Guild.ensure_galatron_timelines``).
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004_galatron_attempts"
down_revision: Union[str, None] = "0003_minecraft_status_channel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "galatron_attempt",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("won", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_galatron_attempt_guild_time", "galatron_attempt", ["guild_id", "occurred_at"]
    )
    op.create_index(
        "ix_galatron_attempt_guild_member", "galatron_attempt", ["guild_id", "member_id"]
    )

    op.create_table(
        "galatron_cooldown",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cooldown_s", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "valid_from"),
    )
    op.create_table(
        "galatron_chance",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chance", sa.Double(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "valid_from"),
    )

    op.execute(
        """
        INSERT INTO galatron_attempt (guild_id, member_id, occurred_at, won)
        SELECT guild_id, member_id, occurred_at, true FROM galatron_history
        """
    )
    op.execute(
        """
        INSERT INTO galatron_cooldown (guild_id, valid_from, cooldown_s)
        SELECT guild_id, TIMESTAMPTZ 'epoch', galatron_cooldown_s FROM guild
        """
    )
    op.execute(
        """
        INSERT INTO galatron_chance (guild_id, valid_from, chance)
        SELECT guild_id, TIMESTAMPTZ 'epoch', galatron_chance FROM guild
        """
    )

    op.drop_table("galatron_member")
    op.drop_index("galatron_history_guild_seq", table_name="galatron_history")
    op.drop_table("galatron_history")
    op.drop_column("guild", "galatron_chance")
    op.drop_column("guild", "galatron_cooldown_s")


def downgrade() -> None:
    op.add_column(
        "guild",
        sa.Column("galatron_chance", sa.Double(), nullable=False, server_default="0.005"),
    )
    op.add_column(
        "guild",
        sa.Column(
            "galatron_cooldown_s", sa.Integer(), nullable=False, server_default="86400"
        ),
    )
    op.create_table(
        "galatron_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "galatron_history_guild_seq", "galatron_history", ["guild_id", "occurred_at", "id"]
    )
    op.create_table(
        "galatron_member",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_times_used", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "member_id"),
    )

    op.execute(
        """
        UPDATE guild g SET
            galatron_cooldown_s = COALESCE((
                SELECT c.cooldown_s FROM galatron_cooldown c
                WHERE c.guild_id = g.guild_id
                ORDER BY c.valid_from DESC LIMIT 1
            ), 86400),
            galatron_chance = COALESCE((
                SELECT c.chance FROM galatron_chance c
                WHERE c.guild_id = g.guild_id
                ORDER BY c.valid_from DESC LIMIT 1
            ), 0.005)
        """
    )
    op.execute(
        """
        INSERT INTO galatron_history (guild_id, member_id, occurred_at)
        SELECT guild_id, member_id, occurred_at FROM galatron_attempt WHERE won
        """
    )
    op.execute(
        """
        INSERT INTO galatron_member (guild_id, member_id, last_used, total_times_used)
        SELECT guild_id, member_id, max(occurred_at), count(*)
        FROM galatron_attempt GROUP BY guild_id, member_id
        """
    )

    op.drop_table("galatron_chance")
    op.drop_table("galatron_cooldown")
    op.drop_index("ix_galatron_attempt_guild_member", table_name="galatron_attempt")
    op.drop_index("ix_galatron_attempt_guild_time", table_name="galatron_attempt")
    op.drop_table("galatron_attempt")
