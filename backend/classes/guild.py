from __future__ import annotations
import logging
from collections import Counter
from typing import TYPE_CHECKING
import random
import discord
from datetime import timedelta, datetime, timezone

from store import galatron_repo, guild_repo, lfg_repo, minecraft_repo, trivia_repo

from . import clock
from .base.guildbase import GuildBase
from .galatron import DEFAULT_CHANCE, GalatronAttempt, GalatronLog
from .galatron_text import Register, next_register
from .generics import SettingTimeline
from .lfg import LFGNotAllowed, LFGHost, LFGChannel
from .minecraft import MinecraftStatusConfig
from .trivia import TriviaChannelConfig

if TYPE_CHECKING:
    from store.state import GuildState

logger = logging.getLogger(__name__)


class Guild(GuildBase):
    __slots__ = (
        "host_roles", "lfg_channels",
        "galatron_role", "galatron_channels", "galatron_log",
        "galatron_chances", "galatron_register",
        "trivia_channels", "minecraft_channels",
    )

    def __init__(
            self, guild: discord.Guild, host_roles: dict[int, LFGHost], lfg_channels: dict[int, LFGChannel],
            galatron_role: discord.Role | None, galatron_channels: list[discord.TextChannel],
            galatron_log: GalatronLog, galatron_chances: SettingTimeline,
            galatron_register: Register,
            trivia_channels: dict[int, TriviaChannelConfig], minecraft_channels: dict[int, MinecraftStatusConfig],
    ):
        super().__init__(guild)

        # lfg stuff
        self.host_roles = host_roles
        self.lfg_channels = lfg_channels

        # galatron stuff
        self.galatron_role = galatron_role
        self.galatron_channels = galatron_channels
        self.galatron_log = galatron_log
        self.galatron_chances = galatron_chances
        self.galatron_register = galatron_register

        # trivia stuff
        self.trivia_channels = trivia_channels

        # minecraft stuff
        self.minecraft_channels = minecraft_channels

        self._instances[self.id] = self

    def get_role_cooldown(self, role: discord.Role) -> timedelta | None:
        if role.id in self.host_roles:
            return self.host_roles[role.id].cooldown
        return None

    def get_member_cooldown(self, member: discord.Member) -> timedelta | LFGNotAllowed:
        results = []
        for role in member.roles:
            result = self.get_role_cooldown(role)
            if isinstance(result, LFGNotAllowed):
                return result
            if result is not None:
                results.append(result)
        if results:
            return min(results)
        return LFGNotAllowed()

    def add_lfg_channel(self, channel: discord.TextChannel, roles: list[discord.Role]) -> None:
        self.lfg_channels[channel.id] = LFGChannel(channel, roles)

    # LFG
    async def set_cooldown(self, role: discord.Role, amount: int, unit: str) -> None:
        if role.id in self.host_roles:
            self.host_roles[role.id].set_cooldown(amount, unit)
        else:
            self.host_roles[role.id] = LFGHost(role, amount, unit)
        await lfg_repo.upsert_host_role(self.id, role.id, amount, unit)

    async def remove_host_role(self, role_id: int) -> None:
        self.host_roles.pop(role_id, None)
        await lfg_repo.delete_host_role(self.id, role_id)

    async def add_lfg_role(self, channel: discord.TextChannel, role: discord.Role) -> bool:
        existing = self.lfg_channels.get(channel.id)
        if existing is not None:
            if any(r.id == role.id for r in existing.roles):
                return False
            existing.roles.append(role)
        else:
            self.add_lfg_channel(channel, [role])
        role_ids = [r.id for r in self.lfg_channels[channel.id].roles]
        await lfg_repo.set_channel_roles(self.id, channel.id, role_ids)
        return True

    async def remove_lfg_channel(self, channel_id: int) -> None:
        self.lfg_channels.pop(channel_id, None)
        await lfg_repo.delete_channel(self.id, channel_id)

    # Galatron
    @property
    def galatron_chance(self) -> float:
        return self.galatron_chances.current

    async def set_galatron_role(self, role: discord.Role | None) -> None:
        self.galatron_role = role
        await guild_repo.set_galatron_role(self.id, role.id if role else None)

    async def set_galatron_chance(self, chance: float) -> None:
        now = clock.now_utc()
        self.galatron_chances.add(chance, now)
        await galatron_repo.add_chance(self.id, chance, now.timestamp())

    async def ensure_galatron_timelines(self, joined_at: datetime) -> None:
        """Give the chance timeline a defined starting point. The bot cannot have had a
        setting before it joined, so a missing timeline starts at the join with the
        current value, and one reaching further back is pulled forward to it (that is
        how the values carried over by the schema migration get their real start)."""
        timeline = self.galatron_chances
        start = timeline.start
        if start is None:
            value = timeline.current
            timeline.add(value, joined_at)
            await galatron_repo.add_chance(self.id, value, joined_at.timestamp())
        elif start < joined_at:
            timeline.periods[0] = (joined_at, timeline.periods[0][1])
            await galatron_repo.move_chance_start(self.id, start.timestamp(), joined_at.timestamp())

    async def add_galatron_channel(self, channel: discord.TextChannel) -> None:
        self.galatron_channels.append(channel)
        await galatron_repo.add_channel(self.id, channel.id)

    async def remove_galatron_channel(self, channel: discord.TextChannel) -> None:
        self.galatron_channels.remove(channel)
        await galatron_repo.delete_channel(self.id, channel.id)

    def galatron_attempts_by_chance(self) -> Counter[float]:
        """How many attempts were made under which win chance — the chance that was in
        force at the time, not today's."""
        counts: Counter[float] = Counter()
        for attempt in self.galatron_log.attempts:
            counts[self.galatron_chances.value_at(attempt.occurred_at)] += 1
        return counts

    async def galatron_record_attempt(self, member: discord.Member, won: bool) -> None:
        occurred_at = clock.now_utc().replace(microsecond=0)
        self.galatron_log.add(member.id, occurred_at, won)
        await galatron_repo.add_attempt(self.id, member.id, occurred_at.timestamp(), won)
        if won:
            self.galatron_register = next_register(self.galatron_register)
            await guild_repo.set_galatron_register(self.id, self.galatron_register)

    async def galatron_reset(self) -> None:
        self.galatron_log = GalatronLog(self.guild)
        await galatron_repo.clear_attempts(self.id)

    # Trivia
    async def set_trivia_channel(self, config: TriviaChannelConfig) -> None:
        self.trivia_channels[config.channel_id] = config
        await trivia_repo.upsert_channel(self.id, config)

    async def update_trivia_channel(self, config: TriviaChannelConfig) -> None:
        await trivia_repo.upsert_channel(self.id, config)

    async def remove_trivia_channel(self, channel_id: int) -> None:
        self.trivia_channels.pop(channel_id, None)
        await trivia_repo.delete_channel(self.id, channel_id)
        await trivia_repo.delete_pending(channel_id)

    # Minecraft
    async def set_minecraft_channel(self, config: MinecraftStatusConfig) -> None:
        self.minecraft_channels[config.channel_id] = config
        await minecraft_repo.upsert_channel(self.id, config.channel_id, config.address)

    async def remove_minecraft_channel(self, channel_id: int) -> None:
        self.minecraft_channels.pop(channel_id, None)
        await minecraft_repo.delete_channel(self.id, channel_id)

    @classmethod
    def from_state(cls, guild: discord.Guild, gs: "GuildState | None"):
        if gs is None:
            return cls(
                guild, {}, {}, None, [], GalatronLog(guild),
                SettingTimeline(DEFAULT_CHANCE),
                random.choice(list(Register)), {}, {},
            )

        # lfg stuff
        host_roles: dict[int, LFGHost] = {}
        for hr in gs.host_roles:
            role = guild.get_role(hr.role_id)
            if role:
                host_roles[hr.role_id] = LFGHost(role, hr.cooldown, hr.unit)

        lfg_channels: dict[int, LFGChannel] = {}
        for lc in gs.lfg_channels:
            channel = guild.get_channel(lc.channel_id)
            if not isinstance(channel, discord.TextChannel):
                logger.warning("channel %s not found or not a text channel", lc.channel_id)
                continue
            roles = [role for rid in lc.role_ids if (role := guild.get_role(rid)) is not None]
            lfg_channels[lc.channel_id] = LFGChannel(channel, roles)

        # galatron stuff
        galatron_role = guild.get_role(gs.galatron_role_id) if gs.galatron_role_id else None
        galatron_channels = [
            c for c in (guild.get_channel(cid) for cid in gs.galatron_channels)
            if isinstance(c, discord.TextChannel)
        ]
        galatron_log = GalatronLog(
            guild,
            [GalatronAttempt(a.member_id, datetime.fromtimestamp(a.occurred_at, timezone.utc), a.won) for a in gs.galatron_attempts],
        )
        galatron_chances = SettingTimeline(
            DEFAULT_CHANCE,
            [(datetime.fromtimestamp(p.valid_from, timezone.utc), p.value) for p in gs.galatron_chances],
        )
        galatron_register = Register(gs.galatron_register) if gs.galatron_register else random.choice(list(Register))

        # trivia stuff
        trivia_channels = {
            tc.channel_id: TriviaChannelConfig(
                tc.channel_id, tc.list_name, tc.schedule, tc.response,
                tc.mode, tc.order, next_index=tc.next_index,
            )
            for tc in gs.trivia_channels
        }

        # minecraft stuff
        minecraft_channels = {
            mc.channel_id: MinecraftStatusConfig(mc.channel_id, mc.address)
            for mc in gs.minecraft_channels
        }

        return cls(
            guild, host_roles, lfg_channels, galatron_role, galatron_channels, galatron_log,
            galatron_chances, galatron_register, trivia_channels, minecraft_channels,
        )
