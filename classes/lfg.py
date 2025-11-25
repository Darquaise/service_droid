from __future__ import annotations
from datetime import timedelta
from typing import TYPE_CHECKING
import discord

from converters import transform_time

if TYPE_CHECKING:
    from .context import Context, ApplicationContext


class LFGNotAllowed:
    pass


def transform_time_lfg(time_amount: int, time_unit: str) -> timedelta | type[LFGNotAllowed] | None:
    time = transform_time(time_amount, time_unit)
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


class LFGHost:
    __slots__ = "role", "channels", "cooldown", "_amount", "_unit"

    def __init__(self, role: discord.Role, time_amount: int, time_unit: str):
        self.role = role
        self.cooldown = transform_time_lfg(time_amount, time_unit)
        self._amount = time_amount
        self._unit = time_unit

    def set_cooldown(self, amount: int, unit: str):
        self.cooldown = transform_time_lfg(amount, unit)
        self._amount = amount
        self._unit = unit

    @classmethod
    def from_json(cls, data: dict, role: discord.Role):
        return cls(role, data['cooldown'], data['cooldown_type'])

    def to_json(self):
        return {
            "id": self.role.id,
            "cooldown": self._amount,
            "cooldown_type": self._unit
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
        roles = [x for x in filter(None, [channel.guild.get_role(role_id) for role_id in data['roles']])]
        return cls(channel, roles)

    def to_json(self):
        return {
            "id": self.channel.id,
            "roles": [role.id for role in self.roles]
        }
