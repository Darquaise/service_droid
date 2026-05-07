import discord
from discord.ext import commands

from .settings import Settings
from .context import Context, ApplicationContext


class ServiceDroid(commands.Bot):
    def __init__(self, settings: Settings = None, *args, **kwargs):
        super().__init__(*args, auto_sync_commands=False, **kwargs)

        self.settings = settings if settings else Settings("settings.json")

    async def get_context(self, message: discord.Message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    async def get_application_context(self, interaction: discord.Interaction, cls=ApplicationContext):
        return await super().get_application_context(interaction, cls=cls)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return
        await self.process_commands(message)

    async def process_application_commands(self, interaction: discord.Interaction, *args, **kwargs) -> None:
        if interaction.guild_id is None:
            return
        await super().process_application_commands(interaction, *args, **kwargs)
