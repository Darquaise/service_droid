from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import TYPE_CHECKING, Iterable
import discord

if TYPE_CHECKING:
    from .context import ApplicationContext

DEFAULT_CHANCE = 0.005
DEFAULT_COOLDOWN_S = 86_400


class GalatronData:
    __slots__ = ("_ctx",)

    def __init__(self, ctx: ApplicationContext):
        self._ctx = ctx

    @property
    def is_galatron_channel(self) -> bool:
        return self._ctx.channel in self._ctx.g.galatron_channels

    @property
    def is_on_cooldown(self) -> datetime | None:
        last_used = self._ctx.g.galatron_log.last_attempt_at(self._ctx.user.id)
        if last_used is None:
            return None

        next_allowed = last_used + self._ctx.g.galatron_cooldown
        return next_allowed if next_allowed > datetime.now() else None

    @property
    def is_current_owner(self) -> bool:
        owner = self.current_owner
        if owner is None:
            return False
        return self._ctx.user.id == owner.id

    @property
    def current_owner(self) -> discord.Member | None:
        return self._ctx.g.galatron_log.get_current_owner()

    @property
    def role(self) -> discord.Role | None:
        return self._ctx.g.galatron_role


@dataclass(slots=True)
class GalatronAttempt:
    member_id: int
    occurred_at: datetime
    won: bool


class GalatronLog:
    """Every attempt ever made in a guild, oldest first; a win is an attempt with
    ``won``. Aggregates (per-member totals, last attempt) are kept alongside so the
    hot paths don't have to walk the list."""

    __slots__ = "guild", "attempts", "_totals", "_last_attempt"

    def __init__(self, guild: discord.Guild, attempts: Iterable[GalatronAttempt] = ()):
        self.guild = guild
        self.attempts = sorted(attempts, key=lambda a: a.occurred_at)
        self._totals: Counter[int] = Counter()
        self._last_attempt: dict[int, datetime] = {}
        for attempt in self.attempts:
            self._index(attempt)

    def _index(self, attempt: GalatronAttempt) -> None:
        self._totals[attempt.member_id] += 1
        previous = self._last_attempt.get(attempt.member_id)
        if previous is None or attempt.occurred_at > previous:
            self._last_attempt[attempt.member_id] = attempt.occurred_at

    def add(self, member_id: int, occurred_at: datetime, won: bool) -> GalatronAttempt:
        attempt = GalatronAttempt(member_id, occurred_at, won)
        self.attempts.append(attempt)
        self._index(attempt)
        return attempt

    @property
    def wins(self) -> list[GalatronAttempt]:
        return [a for a in self.attempts if a.won]

    @property
    def total_attempts(self) -> int:
        return len(self.attempts)

    @property
    def totals(self) -> dict[int, int]:
        """attempts per member id"""
        return self._totals

    def total_for(self, member_id: int) -> int:
        return self._totals.get(member_id, 0)

    def last_attempt_at(self, member_id: int) -> datetime | None:
        return self._last_attempt.get(member_id)

    def get_current_owner(self) -> discord.Member | None:
        for attempt in reversed(self.attempts):
            if attempt.won:
                return self.guild.get_member(attempt.member_id)
        return None

    async def calculate_leaderboard(self) -> list[tuple[discord.Member, timedelta, int]]:
        member_times: dict[int, list] = {}
        times_received: dict[int, int] = {}

        wins = self.wins
        for x, attempt in enumerate(wins):
            member_id = attempt.member_id
            end_time = wins[x + 1].occurred_at if len(wins) > x + 1 else datetime.now()

            if member_id not in member_times:
                member = self.guild.get_member(member_id)
                if not member:
                    try:
                        member = await self.guild.fetch_member(member_id)
                    except discord.NotFound:
                        member = None

                member_times[member_id] = [member, timedelta()]
                times_received[member_id] = 0

            member_times[member_id][1] += end_time - attempt.occurred_at
            times_received[member_id] += 1

        return [
            (member, duration, times_received[member_id])
            for member_id, (member, duration) in member_times.items()
            if member is not None
        ]
