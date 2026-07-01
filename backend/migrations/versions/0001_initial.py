from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guild",
        sa.Column("guild_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("galatron_role_id", sa.BigInteger(), nullable=True),
        sa.Column("galatron_chance", sa.Double(), nullable=False, server_default="0.005"),
        sa.Column("galatron_cooldown_s", sa.Integer(), nullable=False, server_default="86400"),
        sa.PrimaryKeyConstraint("guild_id"),
    )

    op.create_table(
        "lfg_host_role",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("cooldown", sa.Integer(), nullable=False),
        sa.Column("cooldown_unit", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "role_id"),
    )

    op.create_table(
        "lfg_channel",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "channel_id"),
    )

    op.create_table(
        "lfg_channel_role",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["guild_id", "channel_id"],
            ["lfg_channel.guild_id", "lfg_channel.channel_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("guild_id", "channel_id", "role_id"),
    )

    op.create_table(
        "galatron_channel",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "channel_id"),
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
        "galatron_history_guild_seq",
        "galatron_history",
        ["guild_id", "occurred_at", "id"],
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

    op.create_table(
        "trivia_list",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "name"),
    )

    op.create_table(
        "trivia_question",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("list_name", sa.Text(), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("question", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("answer_context", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(
            ["guild_id", "list_name"],
            ["trivia_list.guild_id", "trivia_list.name"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "list_name", "local_id"),
    )

    op.create_table(
        "trivia_channel",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("list_name", sa.Text(), nullable=False),
        sa.Column("schedule", sa.Text(), nullable=False),
        sa.Column("response", sa.Integer(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("question_order", sa.Text(), nullable=False),
        sa.Column("next_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["guild_id"], ["guild.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "channel_id"),
    )

    op.create_table(
        "trivia_pending",
        sa.Column("channel_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("answer_context", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("channel_id"),
    )


def downgrade() -> None:
    op.drop_table("trivia_pending")
    op.drop_table("trivia_channel")
    op.drop_table("trivia_question")
    op.drop_table("trivia_list")
    op.drop_table("galatron_member")
    op.drop_index("galatron_history_guild_seq", table_name="galatron_history")
    op.drop_table("galatron_history")
    op.drop_table("galatron_channel")
    op.drop_table("lfg_channel_role")
    op.drop_table("lfg_channel")
    op.drop_table("lfg_host_role")
    op.drop_table("guild")
