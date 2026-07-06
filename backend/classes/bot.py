from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from store import dispose_engine

from .settings import Settings
from .context import Context, ApplicationContext

if TYPE_CHECKING:
    from store.notify import ChangeListener
    from .minecraft import MinecraftStatusUpdater
    from .trivia_scheduler import TriviaScheduler


class ServiceDroid(commands.Bot):
    def __init__(self, settings: Settings | None = None, *args, **kwargs):
        super().__init__(*args, auto_sync_commands=False, **kwargs)

        self.settings = settings if settings else Settings()
        # set by cogs/startup.py once the DB change-listener is running
        self.change_listener: "ChangeListener | None" = None
        # set by TriviaCog once the scheduler is up
        self.trivia_scheduler: "TriviaScheduler | None" = None
        # set by MinecraftCog once the updater is up
        self.minecraft_updater: "MinecraftStatusUpdater | None" = None

    async def close(self) -> None:
        if self.change_listener is not None:
            await self.change_listener.stop()
        await dispose_engine()
        await super().close()

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
