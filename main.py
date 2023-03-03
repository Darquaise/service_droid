import asyncio
import discord

from classes.bot import ServiceDroid
from cogs.custom import CustomCog
from cogs.settings import SettingsCog


intents = discord.Intents.all()
bot = ServiceDroid(command_prefix="!", help_command=None, debug_guilds=[576380164250927124], intents=intents)


with open("token", "r") as f:
    token = f.read()


async def startup():
    bot.add_cog(CustomCog(bot))
    bot.add_cog(SettingsCog(bot))
    await bot.start(token=token)


asyncio.run(startup())
