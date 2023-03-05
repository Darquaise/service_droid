import discord
from discord.ext import commands
import os

from classes import ServiceDroid


async def shutdown(bot: ServiceDroid):
    activity = discord.Activity(name='shutting down...', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    await bot.close()


async def restart(bot: ServiceDroid):
    activity = discord.Activity(name='restarting...', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    await bot.close()
    os.system("./start.sh")


class DevelopmentCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        print('dev cog loaded')

    async def load_cog(self, extension: str):
        if extension == '*':
            for n in os.listdir('./cogs'):
                if n.endswith('.py'):
                    try:
                        self.bot.load_extension(f'cogs.{n[:-3]}')
                        print(f'Unloaded: {n}')

                    except NameError:
                        return print(f'Load had an error: {NameError}')
        else:
            self.bot.load_extension(f'cogs.{extension}')

    async def unload_cog(self, extension: str):
        if extension == '*':
            for n in os.listdir('./cogs'):
                if n.endswith('.py'):
                    try:
                        self.bot.unload_extension(f'cogs.{n[:-3]}')
                        print(f'Loaded: {n}')

                    except NameError:
                        return print(f'Unload had an error: {NameError}')

        else:
            self.bot.unload_extension(f'cogs.{extension}')

    async def reload_cog(self, extension: str):
        if extension == '*':
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    self.bot.reload_extension(f'cogs.{filename[:-3]}')
                    try:
                        self.bot.reload_extension(f'cogs.{filename[:-3]}')
                    except NameError:
                        return print(f'Reload had an error: {NameError}')
        else:
            self.bot.reload_extension(f'cogs.{extension}')
            print(f'Reloaded: {extension}')

    @discord.application_command(debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def update_git(self, ctx: discord.ApplicationContext):
        os.system('git pull')
        await ctx.respond(
            "Updated project",
            ephemeral=True
        )

    @commands.slash_command(description="Shuts down the Bot", debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def shutdown(self, ctx: discord.ApplicationContext):
        await ctx.respond("Bot is shutting down", ephemeral=True)
        await shutdown(self.bot)

    @commands.slash_command(description="Restarts the Bot", debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def restart(self, ctx: discord.ApplicationContext):
        await ctx.respond("Bot is restarting", ephemeral=True)
        await restart(self.bot)

    @commands.slash_command(name='reload', description='Reload a Bots Cog', debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def cog_reload(self, ctx: discord.ApplicationContext, extension):
        await self.reload_cog(extension)
        await ctx.respond(f"`cogs.{extension}` has been reloaded", ephemeral=True)

    @commands.slash_command(name='load', description='Load a Bots Cog', debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def cog_load(self, ctx: discord.ApplicationContext, extension):
        await self.load_cog(extension)
        await ctx.respond(f"`cogs.{extension}` has been loaded", ephemeral=True)

    @commands.slash_command(name='unload', description='Unload a Bots Cog')
    @discord.default_permissions(administrator=True)
    async def slash_cog_unload(self, ctx: discord.ApplicationContext, extension):
        await self.unload_cog(extension)
        await ctx.respond(f"`cogs.{extension}` has been unloaded", ephemeral=True)
