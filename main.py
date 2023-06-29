import discord

from classes.settings import Settings
from classes.bot import ServiceDroid

from cogs.startup import StartupCog


intents = discord.Intents.all()
settings = Settings("settings.json")

bot = ServiceDroid(
    command_prefix="!",
    case_insensitive=True,
    help_command=None,
    debug_guilds=[576380164250927124] if settings.debug else None,
    intents=intents,
    settings=settings
)

# preload startup cog and start bot
bot.add_cog(StartupCog(bot))
bot.run(token=settings.credentials.token)
