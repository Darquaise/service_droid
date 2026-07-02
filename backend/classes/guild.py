from __future__ import annotations
import logging
from typing import TYPE_CHECKING
import discord
from datetime import timedelta, datetime

from store import galatron_repo, guild_repo, lfg_repo, trivia_repo

from .base.guildbase import GuildBase
from .galatron import GalatronHistory
from .lfg import LFGNotAllowed, LFGHost, LFGChannel
from .trivia import TriviaChannelConfig

if TYPE_CHECKING:
    from store.state import GuildState

logger = logging.getLogger(__name__)


class Guild(GuildBase):
    __slots__ = (
        "host_roles", "lfg_channels",
        "galatron_role", "galatron_chance", "galatron_cooldown", "galatron_channels",
        "galatron_history", "galatron_last_used", "galatron_total_times_used",
        "trivia_channels",
    )

    def __init__(
            self, guild: discord.Guild, host_roles: dict[int, LFGHost], lfg_channels: dict[int, LFGChannel],
            galatron_role: discord.Role | None, galatron_chance: float, galatron_cooldown: timedelta,
            galatron_channels: list[discord.TextChannel], galatron_history: GalatronHistory,
            galatron_last_used: dict[int, datetime], galatron_total_times_used: dict[int, int],
            trivia_channels: dict[int, TriviaChannelConfig]
    ):
        super().__init__(guild)

        # lfg stuff
        self.host_roles = host_roles
        self.lfg_channels = lfg_channels

        # galatron stuff
        self.galatron_role = galatron_role
        self.galatron_chance = galatron_chance
        self.galatron_cooldown = galatron_cooldown
        self.galatron_channels = galatron_channels
        self.galatron_history = galatron_history
        self.galatron_last_used = galatron_last_used
        self.galatron_total_times_used = galatron_total_times_used

        # trivia stuff
        self.trivia_channels = trivia_channels

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
    async def set_galatron_role(self, role: discord.Role | None) -> None:
        self.galatron_role = role
        await guild_repo.set_galatron_role(self.id, role.id if role else None)

    async def set_galatron_chance(self, chance: float) -> None:
        self.galatron_chance = chance
        await guild_repo.set_galatron_chance(self.id, chance)

    async def set_galatron_cooldown(self, cooldown: timedelta) -> None:
        self.galatron_cooldown = cooldown
        await guild_repo.set_galatron_cooldown(self.id, int(cooldown.total_seconds()))

    async def add_galatron_channel(self, channel: discord.TextChannel) -> None:
        self.galatron_channels.append(channel)
        await galatron_repo.add_channel(self.id, channel.id)

    async def remove_galatron_channel(self, channel: discord.TextChannel) -> None:
        self.galatron_channels.remove(channel)
        await galatron_repo.delete_channel(self.id, channel.id)

    async def galatron_register_attempt(self, member: discord.Member) -> None:
        now = datetime.now().replace(microsecond=0)
        self.galatron_last_used[member.id] = now
        total = await galatron_repo.register_attempt(self.id, member.id, now.timestamp())
        self.galatron_total_times_used[member.id] = total

    async def galatron_add_win(self, member: discord.Member) -> None:
        ts = datetime.now().replace(microsecond=0)
        self.galatron_history.add_entry(member, ts)
        await galatron_repo.append_history(self.id, member.id, ts.timestamp())

    async def galatron_increment_total(self, member: discord.Member) -> None:
        total = await galatron_repo.increment_total(self.id, member.id)
        self.galatron_total_times_used[member.id] = total

    async def galatron_reset(self) -> None:
        self.galatron_history = GalatronHistory(self.guild, [])
        self.galatron_last_used = {}
        self.galatron_total_times_used = {}
        await galatron_repo.clear_galatron(self.id)

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

    @classmethod
    def from_state(cls, guild: discord.Guild, gs: "GuildState | None"):
        if gs is None:
            return cls(
                guild, {}, {}, None, 0.005, timedelta(days=1), [],
                GalatronHistory(guild, []), {}, {}, {},
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
            roles = [r for r in (guild.get_role(rid) for rid in lc.role_ids) if r]
            lfg_channels[lc.channel_id] = LFGChannel(channel, roles)

        # galatron stuff
        galatron_role = guild.get_role(gs.galatron_role_id) if gs.galatron_role_id else None
        galatron_cooldown = timedelta(seconds=gs.galatron_cooldown_s)
        galatron_channels = [
            c for c in (guild.get_channel(cid) for cid in gs.galatron_channels)
            if isinstance(c, discord.TextChannel)
        ]
        galatron_history = GalatronHistory(
            guild,
            [{"timestamp": e.occurred_at, "member_id": e.member_id} for e in gs.galatron_history],
        )

        cutoff = datetime.now() - galatron_cooldown
        galatron_last_used = {
            m.member_id: ts
            for m in gs.galatron_members
            if m.last_used is not None and (ts := datetime.fromtimestamp(m.last_used)) >= cutoff
        }
        galatron_total_times_used = {m.member_id: m.total for m in gs.galatron_members}

        # trivia stuff
        trivia_channels = {
            tc.channel_id: TriviaChannelConfig(
                tc.channel_id, tc.list_name, tc.schedule, tc.response,
                tc.mode, tc.order, next_index=tc.next_index,
            )
            for tc in gs.trivia_channels
        }

        return cls(
            guild, host_roles, lfg_channels,
            galatron_role, gs.galatron_chance, galatron_cooldown, galatron_channels,
            galatron_history, galatron_last_used, galatron_total_times_used,
            trivia_channels,
        )
