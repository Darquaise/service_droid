from __future__ import annotations
from datetime import timedelta
from typing import TYPE_CHECKING
import discord

from converters import dec2rgba

if TYPE_CHECKING:
    from .context import Context, ApplicationContext


class LFGNotAllowed:
    pass


def transform_time(time_amount: int, time_unit: str) -> timedelta | type[LFGNotAllowed] | None:

    if time_unit == 'days':
        time = timedelta(days=time_amount)
    elif time_unit == 'hours':
        time = timedelta(hours=time_amount)
    elif time_unit == 'minutes':
        time = timedelta(minutes=time_amount)
    elif time_unit == 'seconds':
        time = timedelta(seconds=time_amount)
    else:
        return None

    return time if time > timedelta() else LFGNotAllowed


class LFGData:
    def __init__(self, ctx: Context | ApplicationContext):
        self._ctx = ctx

    @property
    def is_lfg_channel(self) -> bool:
        return self._ctx.channel.id in self._ctx.g.lfg_channels

    @property
    def roles(self) -> list[discord.Role] | None:
        if self.is_lfg_channel:
            return self._ctx.g.lfg_channels[self._ctx.channel.id].roles
        return None

    @property
    def roles_str(self) -> list[str]:
        return [role.mention for role in self.roles]


class TrustedHost:
    __slots__ = "role", "channels", "cooldown", "_amount", "_unit"

    def __init__(self, role: discord.Role, time_amount: int, time_unit: str):
        self.role = role
        self.cooldown = transform_time(time_amount, time_unit)
        self._amount = time_amount
        self._unit = time_unit

    def set_cooldown(self, amount: int, unit: str):
        self.cooldown = transform_time(amount, unit)
        self._amount = amount
        self._unit = unit

    @classmethod
    def from_json(cls, data: dict, role: discord.Role):
        return cls(role, data['cooldown'], data['cooldown_type'])

    def to_json(self):
        return {
            'id': str(self.role.id),
            'name': self.role.name,
            'color': dec2rgba(self.role.color.value),
            'bg_color': dec2rgba(self.role.color.value, 0.5),
            'cooldown': self._amount,
            'cooldown_type': self._unit
        }


class LFGChannel:
    __slots__ = "channel", "roles"

    def __init__(self, channel: discord.TextChannel, roles: list[discord.Role]):
        self.channel = channel
        self.roles = roles

    def remove_role(self, role_id: int) -> bool:
        for role in self.roles:
            if role.id == role_id:
                self.roles.remove(role)
                return True
        return False

    @classmethod
    def from_json(cls, data: dict, channel: discord.TextChannel):
        roles = [x for x in filter(None, [channel.guild.get_role(int(role['id'])) for role in data['roles']])]
        return cls(channel, roles)

    def to_json(self):

        return {
            'id': str(self.channel.id),
            'name': self.channel.name,
            'roles': [
                {
                    'id': str(role.id),
                    'name': role.name,
                    'color': dec2rgba(role.color.value),
                    'bg_color': dec2rgba(role.color.value, 0.5)
                } for role in self.roles
            ]
        }


