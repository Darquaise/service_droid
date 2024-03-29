from __future__ import annotations
import discord
from datetime import timedelta

from .base.guildbase import GuildBase
from .lfg import LFGNotAllowed, TrustedHost, LFGChannel


class Guild(GuildBase):
    def __init__(self, guild: discord.Guild, roles: dict[int, TrustedHost], channels: dict[int, LFGChannel]):
        super().__init__()  # doesn't actually do anything, just so python doesn't complain

        self.guild = guild
        self.lfg_roles = roles
        self.lfg_channels = channels

        self._instances[self.id] = self

    def get_role_cooldown(self, role: discord.Role) -> timedelta | None:
        if role.id in self.lfg_roles:
            return self.lfg_roles[role.id].cooldown
        return None

    def get_member_cooldown(self, member: discord.Member) -> timedelta | type[LFGNotAllowed]:
        for role in reversed(member.roles):
            result = self.get_role_cooldown(role)
            if result:
                return result
        return LFGNotAllowed

    def add_lfg_channel(self, channel: discord.TextChannel, roles: list[discord.Role]) -> None:
        self.lfg_channels[channel.id] = LFGChannel(channel, roles)

    def set_cooldown(self, role: discord.Role, amount, unit) -> None:
        if role.id in self.lfg_roles:
            self.lfg_roles[role.id].set_cooldown(amount, unit)
        else:
            self.lfg_roles[role.id] = TrustedHost(role, amount, unit)

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
        roles: dict[int, TrustedHost] = {}
        for role_data in data['roles']:
            role = guild.get_role(role_data['id'])
            if role:
                roles[role_data['id']] = TrustedHost.from_json(role_data, role)

        channels: dict[int, LFGChannel] = {}
        for channel_data in data['channels']:
            channel = guild.get_channel(channel_data['id'])
            if channel:
                channels[channel_data['id']] = LFGChannel.from_json(channel_data, channel)
            else:
                print(f"channel {channel_data['id']} not found")

        return cls(guild, roles, channels)

    def to_json(self):
        return {
            "roles": [role.to_json() for role in self.lfg_roles.values()],
            "channels": [channel.to_json() for channel in self.lfg_channels.values()]
        }
