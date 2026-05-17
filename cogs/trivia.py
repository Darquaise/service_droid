from discord.ext import commands

from classes import ServiceDroid, Guild, TriviaScheduler


class TriviaCog(commands.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        self.scheduler = TriviaScheduler(bot)
        bot.trivia_scheduler = self.scheduler
        bot.loop.create_task(self._initial_schedule())

    async def _initial_schedule(self):
        await self.bot.wait_until_ready()
        for guild in Guild.get_all():
            for cid, cfg in guild.trivia_channels.items():
                self.scheduler.schedule_channel(cid, cfg)

    def cog_unload(self):
        self.scheduler.cancel_all()
