import discord

from classes import Settings
from classes import ServiceDroid

from cogs.startup import StartupCog


intents = discord.Intents.all()
settings = Settings("settings.json")

bot = ServiceDroid(
    command_prefix="!",
    case_insensitive=True,
    help_command=None,
    debug_guilds=[576380164250927124] if settings.debug else None,
    intents=intents,
    settings=settings,
    owner_ids={264203029279014922}
)
bot.exit_code = 0

# get token from token file
with open("token", "r") as f:
    token = f.read()

# preload startup cog and start bot
bot.add_cog(StartupCog(bot))
bot.run(token=token)
code = getattr(bot, "exit_code", 0)
print("code:", code)
if code != 0:
    raise SystemExit(code)
