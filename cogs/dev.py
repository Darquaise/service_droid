import asyncio

import discord
from discord.ext import commands
import os

from classes import ServiceDroid

REPO_PATH = "/home/bot/bots/service_droid"


async def shutdown(bot: ServiceDroid):
    activity = discord.Activity(name='shutting down...', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    await bot.close()


async def restart(bot: ServiceDroid):
    activity = discord.Activity(name='restarting...', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    bot.exit_code = 42
    await bot.close()


class DevelopmentCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        print('dev cog loaded')

    @discord.slash_command(debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def update_git(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        proc = await asyncio.create_subprocess_shell(
            "git pull",
            cwd=REPO_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        code = proc.returncode

        if code == 0:
            msg = stdout.decode().strip() or "No output"
            text = f"git pull successful:\n```{msg}```"
        else:
            out = (stdout.decode() + "\n" + stderr.decode()).strip()
            text = f"git pull failed (code {code}):\n```{out[:1800]}```"

        await ctx.followup.send(text, ephemeral=True)

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
    async def reload_cog(self, ctx: discord.ApplicationContext, extension):
        if extension == '*':
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    self.bot.reload_extension(f'cogs.{filename[:-3]}')
                    try:
                        self.bot.reload_extension(f'cogs.{filename[:-3]}')
                    except NameError:
                        print(f'Reload had an error: {NameError}')
                        break
        else:
            self.bot.reload_extension(f'cogs.{extension}')
            print(f'Reloaded: {extension}')

        await ctx.respond(f"`cogs.{extension}` has been reloaded", ephemeral=True)

    @commands.slash_command(name='load', description='Load a Bots Cog', debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def load_cog(self, ctx: discord.ApplicationContext, extension):
        if extension == '*':
            for n in os.listdir('./cogs'):
                if n.endswith('.py'):
                    try:
                        self.bot.load_extension(f'cogs.{n[:-3]}')
                        print(f'Unloaded: {n}')

                    except NameError:
                        print(f'Load had an error: {NameError}')
                        break
        else:
            self.bot.load_extension(f'cogs.{extension}')

        await ctx.respond(f"`cogs.{extension}` has been loaded", ephemeral=True)

    @commands.slash_command(name='unload', description='Unload a Bots Cog', debug_guilds=[576380164250927124])
    async def unload_cog(self, ctx: discord.ApplicationContext, extension):
        if extension == '*':
            for n in os.listdir('./cogs'):
                if n.endswith('.py'):
                    try:
                        self.bot.unload_extension(f'cogs.{n[:-3]}')
                        print(f'Loaded: {n}')

                    except NameError:
                        print(f'Unload had an error: {NameError}')
                        break

        else:
            self.bot.unload_extension(f'cogs.{extension}')

        await ctx.respond(f"`cogs.{extension}` has been unloaded", ephemeral=True)


def setup(bot):
    bot.add_cog(DevelopmentCog(bot))
