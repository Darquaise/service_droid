import logging

import discord
from discord.ext import commands

from classes import ServiceDroid, Guild, TriviaHandler
from cogs.events import EventsCog
from cogs.galatron_commands import GalatronCog
from cogs.galatron_settings import GalatronSettingsCog

from cogs.lfg_commands import LFGCog
from cogs.lfg_settings import LFGSettingsCog
from cogs.dev import DevelopmentCog
from cogs.logging_cog import LoggingCog
from cogs.trivia import TriviaCog
from cogs.trivia_settings import TriviaSettingsCog

logger = logging.getLogger(__name__)


class StartupCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        bot.loop.create_task(self.startup())

    async def startup(self):
        # start
        logger.info("starting up...")
        await self.bot.wait_until_ready()

        # pre-setup
        logger.info("connection established")

        activity = discord.Activity(name='Starting...', type=discord.ActivityType.playing)
        await self.bot.change_presence(activity=activity)

        # setup
        # --> load guilds
        guilds_data = self.bot.settings.get_guilds_data()
        logger.debug("loaded guilds data: %s", guilds_data)
        for guild in self.bot.guilds:
            if str(guild.id) in guilds_data:  # string because json makes keys strings
                Guild.from_json(guild, guilds_data[str(guild.id)])
            else:
                Guild.from_nothing(guild)
        self.bot.settings.update_guilds()
        logger.info("loaded %d guild(s)", len(self.bot.guilds))

        # --> load trivia handlers
        TriviaHandler.load_all(self.bot.settings.trivia_path, self.bot)

        # --> load cogs
        logger.info("loading cogs...")
        self.bot.add_cog(LFGCog(self.bot))
        self.bot.add_cog(GalatronCog(self.bot))
        self.bot.add_cog(LFGSettingsCog(self.bot))
        self.bot.add_cog(GalatronSettingsCog(self.bot))
        self.bot.add_cog(DevelopmentCog(self.bot))
        self.bot.add_cog(LoggingCog(self.bot))
        self.bot.add_cog(EventsCog(self.bot))
        self.bot.add_cog(TriviaCog(self.bot))
        self.bot.add_cog(TriviaSettingsCog(self.bot))
        logger.info("cogs loaded")

        logger.info("registering slash commands...")
        await self.bot.sync_commands()
        logger.info("slash commands registered")

        # set activity to bot version
        activity = discord.Activity(name='Stellaris', type=discord.ActivityType.playing)
        await self.bot.change_presence(activity=activity)

        logger.info("startup finished")
