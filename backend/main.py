import logging
import os
import discord
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


from classes import Settings, ServiceDroid
from cogs.startup import StartupCog
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
settings = Settings()

bot = ServiceDroid(
    command_prefix=settings.command_prefix,
    case_insensitive=True,
    help_command=None,
    debug_guilds=settings.debug_guild_ids if settings.debug else None,
    intents=intents,
    settings=settings,
    owner_ids=set(settings.owner_ids)
)
bot.exit_code = 0

token = os.environ["DISCORD_TOKEN"]

# preload startup cog and start bot
bot.add_cog(StartupCog(bot))
try:
    bot.run(token=token)
except RuntimeError as e:
    if getattr(bot, "exit_code", 0) == 0:
        raise
    logger.warning("bot.run raised during requested shutdown: %s", e)

code = getattr(bot, "exit_code", 0)
logger.info("exit code: %s", code)
if code != 0:
    raise SystemExit(code)
