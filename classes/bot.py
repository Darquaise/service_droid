import discord
from discord.ext import commands

from .settings import Settings
from .context import Context, ApplicationContext


class ServiceDroid(commands.Bot):
    def __init__(self, settings: Settings = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings = settings if settings else Settings("settings.json")

    async def get_context(self, message: discord.Message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    async def get_application_context(self, interaction: discord.Interaction, cls=ApplicationContext):
        return await super().get_application_context(interaction, cls=cls)
