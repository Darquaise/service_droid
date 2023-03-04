import discord

from classes.bot import ServiceDroid

from cogs.startup import StartupCog


intents = discord.Intents.all()
bot = ServiceDroid(command_prefix="!", help_command=None, debug_guilds=[576380164250927124], intents=intents)


with open("token", "r") as f:
    token = f.read()


bot.add_cog(StartupCog(bot))
bot.run(token=token)
