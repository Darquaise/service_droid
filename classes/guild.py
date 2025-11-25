from __future__ import annotations
import discord
from datetime import timedelta, datetime

from .base.guildbase import GuildBase
from .galatron import GalatronHistory
from .lfg import LFGNotAllowed, LFGHost, LFGChannel


class Guild(GuildBase):
    __slots__ = (
            GuildBase.__slots__ + (
        "host_roles", "lfg_channels", "galatron_role", "galatron_chance", "galatron_cooldown", "galatron_channels",
        "galatron_history", "galatron_last_used", "galatron_total_times_used"))

    def __init__(
            self, guild: discord.Guild, host_roles: dict[int, LFGHost], lfg_channels: dict[int, LFGChannel],
            galatron_role: discord.Role | None, galatron_chance: float, galatron_cooldown: timedelta,
            galatron_channels: list[discord.TextChannel], galatron_history: GalatronHistory,
            galatron_last_used: dict[int, datetime], galatron_total_times_used: dict[int, int]
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

        self._instances[self.id] = self

    def get_role_cooldown(self, role: discord.Role) -> timedelta | None:
        if role.id in self.host_roles:
            return self.host_roles[role.id].cooldown
        return None

    def get_member_cooldown(self, member: discord.Member) -> timedelta | type[LFGNotAllowed]:
        results = []
        for role in member.roles:
            result = self.get_role_cooldown(role)
            if result:
                results.append(result)
        if len(results) > 0:
            return min(results) if min(results) != 0 else LFGNotAllowed
        return LFGNotAllowed

    def add_lfg_channel(self, channel: discord.TextChannel, roles: list[discord.Role]) -> None:
        self.lfg_channels[channel.id] = LFGChannel(channel, roles)

    def set_cooldown(self, role: discord.Role, amount, unit) -> None:
        if role.id in self.host_roles:
            self.host_roles[role.id].set_cooldown(amount, unit)
        else:
            self.host_roles[role.id] = LFGHost(role, amount, unit)

    def remove_lfg_role(self, channel_id: int, role_id: int):
        if channel_id not in self.lfg_channels.keys():
            return

        channel = self.lfg_channels[channel_id]

        for role in channel.roles:
            if role.id == role_id:
                if len(channel.roles) > 1:
                    channel.remove_role(role_id)
                else:
                    del self.lfg_channels[channel_id]

    @classmethod
    def from_json(cls, guild: discord.Guild, data: dict):
        # lfg stuff
        host_roles: dict[int, LFGHost] = {}
        for role_data in data['roles']:
            role_id = int(role_data['id'])
            role = guild.get_role(role_id)
            if role:
                host_roles[role_id] = LFGHost.from_json(role_data, role)

        lfg_channels: dict[int, LFGChannel] = {}
        for channel_data in data['channels']:
            channel_id = int(channel_data['id'])
            channel = guild.get_channel(channel_id)
            if channel:
                lfg_channels[channel_id] = LFGChannel.from_json(channel_data, channel)
            else:
                print(f"channel {channel_id} not found")

        # galatron stuff
        if "galatron" in data:
            ga_data = data['galatron']
            galatron_role = guild.get_role(ga_data['role'])
            galatron_chance = ga_data['chance']
            galatron_cooldown = timedelta(seconds=ga_data['cooldown'])
            galatron_channels = [guild.get_channel(channel_id) for channel_id in ga_data['channels']]
            galatron_history = GalatronHistory(guild, ga_data['history'])

            cutoff = datetime.now() - galatron_cooldown
            galatron_last_used = {
                member_id: ts
                for member_id, raw_ts in ga_data['last_used'].items()
                if (ts := datetime.fromtimestamp(raw_ts)) < cutoff}
            galatron_total_times_used = data['total_times_used'] if 'total_times_used' in data else {}
        else:
            galatron_role = None
            galatron_chance = 0.005
            galatron_cooldown = timedelta(days=1)
            galatron_channels = []
            galatron_history = GalatronHistory(guild, [])
            galatron_last_used = {}
            galatron_total_times_used = {}

        return cls(
            guild, host_roles, lfg_channels,
            galatron_role, galatron_chance, galatron_cooldown, galatron_channels,
            galatron_history, galatron_last_used, galatron_total_times_used
        )

    def to_json(self):
        return {
            "name": self.guild.name,
            "roles": [role.to_json() for role in self.host_roles.values()],
            "channels": [channel.to_json() for channel in self.lfg_channels.values()],
            "galatron": {
                "role": self.galatron_role.id if self.galatron_role else None,
                "chance": self.galatron_chance,
                "cooldown": self.galatron_cooldown.days * 86_400 + self.galatron_cooldown.seconds,
                "channels": [x.id for x in self.galatron_channels],
                "history": self.galatron_history.history,
                "last_used": {member_id: timestamp.timestamp() for member_id, timestamp in
                              self.galatron_last_used.items()},
                "total_times_used": self.galatron_total_times_used
            }
        }

    @classmethod
    def from_nothing(cls, guild: discord.Guild):
        return cls(guild, {}, {}, None, 0.005, timedelta(days=1), [], GalatronHistory(guild, []), {}, {})
