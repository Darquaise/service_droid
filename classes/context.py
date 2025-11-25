import discord
from discord.ext import commands
from typing import TYPE_CHECKING

from .galatron import GalatronData
from .guild import Guild
from .lfg import LFGData

if TYPE_CHECKING:
    from .bot import ServiceDroid


class Context(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot: ServiceDroid
        self.lfg = LFGData(self)
        self.galatron = GalatronData(self)

    @property
    def g(self) -> Guild:
        return Guild.get(self.message.guild.id)

    @property
    def own_perms(self) -> discord.Permissions:
        return self.channel.permissions_for(self.message.guild.me)


class ApplicationContext(discord.ApplicationContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot: ServiceDroid
        self.lfg = LFGData(self)
        self.galatron = GalatronData(self)

    @property
    def g(self) -> Guild:
        return Guild.get(self.interaction.guild_id)

    @property
    def own_perms(self) -> discord.Permissions:
        print("own perms", self.message)
        return self.channel.permissions_for(self.guild.me)
