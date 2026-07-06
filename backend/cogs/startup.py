import logging
from functools import partial
import discord
from discord.ext import commands

from store import guild_repo, init_engine, load_state
from store.notify import ChangeListener
from classes import ServiceDroid, Guild, TriviaHandler, reload_guild
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

    # noinspection PyBroadException
    async def startup(self):
        try:
            await self._startup()
        except Exception:
            logger.exception("startup failed; shutting down")
            self.bot.exit_code = 1
            await self.bot.close()

    async def _startup(self):
        # start
        logger.info("starting up...")
        await self.bot.wait_until_ready()

        # pre-setup
        logger.info("connection established")

        activity = discord.Activity(name='Starting...', type=discord.ActivityType.playing)
        await self.bot.change_presence(activity=activity)

        # setup
        # --> open the database, make sure every current guild has a row
        init_engine(self.bot.settings.database_url)
        await guild_repo.ensure_guilds([(g.id, g.name) for g in self.bot.guilds])

        # --> load guilds from the database into the in-memory registry
        state = await load_state()
        for guild in self.bot.guilds:
            Guild.from_state(guild, state.guilds.get(guild.id))
        logger.info("loaded %d guild(s)", len(self.bot.guilds))

        # --> load trivia handlers
        TriviaHandler.load_from_state(self.bot, state.trivia)

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

        # --> start the live DB-sync listener
        change_listener = ChangeListener(
            self.bot.settings.database_url, partial(reload_guild, self.bot)
        )
        change_listener.start(self.bot.loop)
        self.bot.change_listener = change_listener

        logger.info("registering slash commands...")
        await self.bot.sync_commands()
        logger.info("slash commands registered")

        # set activity to bot version
        activity = discord.Activity(name='Stellaris', type=discord.ActivityType.playing)
        await self.bot.change_presence(activity=activity)

        logger.info("startup finished")
