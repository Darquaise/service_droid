import discord
from discord.ext import commands

from classes import ServiceDroid
from converters.time import dt_now_as_text

from cogs.custom import CustomCog
from cogs.settings import SettingsCog
from cogs.dev import DevelopmentCog


class StartupCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        bot.loop.create_task(self.startup())

    async def startup(self):
        # start
        print(f'[{dt_now_as_text()}] starting up...')
        await self.bot.wait_until_ready()

        # pre-setup
        print(f'[{dt_now_as_text()}] connection established')

        activity = discord.Activity(name=f'Starting...', type=discord.ActivityType.playing)
        await self.bot.change_presence(activity=activity)

        # setup
        # --> load cogs
        print(f'[{dt_now_as_text()}] loading cogs...')
        self.bot.add_cog(CustomCog(self.bot))
        self.bot.add_cog(SettingsCog(self.bot))
        self.bot.add_cog(DevelopmentCog(self.bot))
        print(f'[{dt_now_as_text()}] cogs loaded')

        print(f'[{dt_now_as_text()}] registering slash commands...')
        await self.bot.sync_commands()
        print(f'[{dt_now_as_text()}] slash commands registered')

        # set activity to bot version
        activity = discord.Activity(name='Stellaris', type=discord.ActivityType.playing)
        await self.bot.change_presence(activity=activity)

        print(f'[{dt_now_as_text()}] startup finished...')
