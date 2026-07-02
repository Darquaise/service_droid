import logging
from discord.ext import commands

from store import trivia_repo
from classes import ServiceDroid, Guild, TriviaScheduler

logger = logging.getLogger(__name__)


class TriviaCog(commands.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        self.scheduler = TriviaScheduler(bot)
        bot.trivia_scheduler = self.scheduler
        bot.loop.create_task(self._initial_schedule())

    async def _initial_schedule(self):
        try:
            await self.bot.wait_until_ready()
            pending_data = await trivia_repo.load_pending()
            for guild in Guild.get_all():
                for cid, cfg in guild.trivia_channels.items():
                    raw = pending_data.get(str(cid))
                    if raw is not None:
                        cfg.pending = raw
                    self.scheduler.schedule_channel(cid, cfg)
        except Exception:
            logger.exception("initial trivia scheduling failed")

    def cog_unload(self):
        self.scheduler.cancel_all()
