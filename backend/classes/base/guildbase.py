from __future__ import annotations
import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..guild import Guild


class GuildBase:
    __slots__ = "roles", "channels", "guild",

    _instances: dict[int, Guild] = {}

    def __init__(self, guild: discord.Guild, *args, **kwargs):
        self.guild = guild

    # guild specific stuff
    @classmethod
    def get(cls, guild_id: int) -> Guild:
        return cls._instances.get(guild_id)

    @classmethod
    def get_all(cls):
        return cls._instances.values()

    @classmethod
    async def load(cls, g: discord.Guild, data: dict):
        return cls(g, data)

    @classmethod
    async def delete(cls, guild_id):
        del cls._instances[guild_id]

    # redirects to original guild object
    @property
    def id(self):
        return self.guild.id

    @property
    def name(self):
        return self.guild.name

    @property
    def icon(self) -> discord.Asset | None:
        return self.guild.icon

    @property
    def me(self):
        return self.guild.me

    @property
    def owner(self):
        return self.guild.owner

    @property
    def voice_client(self) -> discord.VoiceClient | None:
        return self.guild.voice_client

    @property
    def vc(self) -> discord.VoiceClient | None:
        return self.voice_client

    @property
    def self_role(self) -> discord.Role | None:
        return self.guild.self_role

    def get_channel(self, channel_id: int):
        return self.guild.get_channel(channel_id)
