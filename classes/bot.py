import discord
from discord.ext import commands

from .settings import Settings


class ServiceDroid(commands.Bot):
    def __init__(self, settings: Settings = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings = settings if settings else Settings("settings.json")
