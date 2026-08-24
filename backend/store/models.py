from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GuildRow(Base):
    """discord guilds with their base settings"""
    __tablename__ = "guild"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    galatron_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class LfgHostRoleRow(Base):
    """LFG host roles with their cooldown"""

    __tablename__ = "lfg_host_role"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cooldown: Mapped[int] = mapped_column(Integer, nullable=False)          # amount
    cooldown_unit: Mapped[str] = mapped_column(Text, nullable=False)        # cooldown_type

    __table_args__ = (PrimaryKeyConstraint("guild_id", "role_id"),)


class LfgChannelRow(Base):
    """LFG channels"""

    __tablename__ = "lfg_channel"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("guild_id", "channel_id"),)


class LfgChannelRoleRow(Base):
    """roles mentioned in a LFG channel"""

    __tablename__ = "lfg_channel_role"

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("guild_id", "channel_id", "role_id"),
        ForeignKeyConstraint(
            ["guild_id", "channel_id"],
            ["lfg_channel.guild_id", "lfg_channel.channel_id"],
            ondelete="CASCADE",
        ),
    )


class GalatronChannelRow(Base):
    """channels the Galatron can be claimed in"""

    __tablename__ = "galatron_channel"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("guild_id", "channel_id"),)


class GalatronAttemptRow(Base):
    """every single Galatron attempt (append-only); a win is an attempt with ``won``"""

    __tablename__ = "galatron_attempt"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("ix_galatron_attempt_guild_time", "guild_id", "occurred_at"),
        Index("ix_galatron_attempt_guild_member", "guild_id", "member_id"),
    )


class GalatronCooldownRow(Base):
    """cooldown between two attempts, as a timeline: each row starts a new period"""

    __tablename__ = "galatron_cooldown"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cooldown_s: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("guild_id", "valid_from"),)


class GalatronChanceRow(Base):
    """win chance per attempt, as a timeline: each row starts a new period"""

    __tablename__ = "galatron_chance"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chance: Mapped[float] = mapped_column(Double, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("guild_id", "valid_from"),)


class MinecraftStatusChannelRow(Base):
    """voice channels mirroring a Minecraft server's status in their name"""

    __tablename__ = "minecraft_status_channel"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("guild_id", "channel_id"),)


class TriviaListRow(Base):
    """a list of trivia questions"""

    __tablename__ = "trivia_list"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("guild_id", "name"),)


class TriviaQuestionRow(Base):
    """a question from a trivia question list"""

    __tablename__ = "trivia_question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    list_name: Mapped[str] = mapped_column(Text, nullable=False)
    local_id: Mapped[int] = mapped_column(Integer, nullable=False)          # the list-local 'id'
    title: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_context: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    __table_args__ = (
        UniqueConstraint("guild_id", "list_name", "local_id"),
        ForeignKeyConstraint(
            ["guild_id", "list_name"],
            ["trivia_list.guild_id", "trivia_list.name"],
            ondelete="CASCADE",
        ),
    )


class TriviaChannelRow(Base):
    """per-channel trivia schedule"""

    __tablename__ = "trivia_channel"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guild.guild_id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    list_name: Mapped[str] = mapped_column(Text, nullable=False)
    schedule: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    question_order: Mapped[str] = mapped_column(Text, nullable=False)  # how the next question is picked (random/sequential); 'order' is reserved in SQL
    next_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        PrimaryKeyConstraint("guild_id", "channel_id"),
        ForeignKeyConstraint(
            ["guild_id", "list_name"],
            ["trivia_list.guild_id", "trivia_list.name"],
            deferrable=True,
            initially="DEFERRED",
        ),
    )


class TriviaPendingRow(Base):
    """unrevealed answers"""

    __tablename__ = "trivia_pending"

    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, server_default="")  # the wording actually posted
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_context: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
