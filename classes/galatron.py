from __future__ import annotations
from datetime import timedelta, datetime
from typing import TYPE_CHECKING
import discord

if TYPE_CHECKING:
    from .context import Context, ApplicationContext


class GalatronData:
    def __init__(self, ctx: Context | ApplicationContext):
        self._ctx = ctx

    @property
    def is_galatron_channel(self) -> bool:
        return self._ctx.channel in self._ctx.g.galatron_channels

    @property
    def is_current_owner(self) -> bool:
        return self._ctx.user.id == self.current_owner.id if self.current_owner else None

    @property
    def current_owner(self) -> discord.Member | None:
        return self._ctx.g.galatron_history.get_current_owner()

    @property
    def role(self) -> discord.Role | None:
        return self._ctx.g.galatron_role


class GalatronHistory:
    __slots__ = "guild", "history"

    def __init__(self, guild: discord.Guild, raw_history: list[dict[str, int]]):
        self.guild = guild
        self.history = raw_history

    def add_entry(self, member: discord.Member, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now()

        self.history.append({"timestamp": timestamp.timestamp(), "member_id": member.id})

    def get_current_owner(self) -> discord.Member | None:
        if len(self.history) == 0:
            return None
        return self.guild.get_member(self.history[-1]["member_id"])

    def calculate_leaderboard(self) -> list[tuple[discord.Member, timedelta, int]]:
        member_times: dict[int, timedelta] = {}
        times_received: dict[int, int] = {}

        for x, entry in enumerate(self.history):
            timestamp = datetime.fromtimestamp(entry["timestamp"])
            member_id = entry["member_id"]

            end_time = datetime.fromtimestamp(self.history[x + 1]["timestamp"]) if len(
                self.history) > x + 1 else datetime.now()

            if member_id not in member_times:
                member_times[member_id] = timedelta()
                times_received[member_id] = 0

            member_times[member_id] += end_time - timestamp
            times_received[member_id] += 1

        return [
            (member, duration, times_received[member_id])
            for member_id, duration in member_times.items()
            if (member := self.guild.get_member(member_id)) is not None
        ]
