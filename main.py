import os
import discord

from classes import Settings
from classes import ServiceDroid

from cogs.startup import StartupCog


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
    print(f"bot.run raised during requested shutdown: {e}")

code = getattr(bot, "exit_code", 0)
print("code:", code)
if code != 0:
    raise SystemExit(code)
