import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from classes import ServiceDroid, LogView, TriviaHandler, TriviaQuestion
from classes.log_view import DEFAULT_LINES_PER_PAGE, LINES_PER_PAGE_OPTIONS

REPO_PATH = str(Path(__file__).resolve().parent.parent)
LOG_PATH = f"{REPO_PATH}/logs/latest.log"

REPO_PATH = "/root/bots/service_droid"


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

    @commands.slash_command(description="Check if Bot responds", debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def status(self, ctx: discord.ApplicationContext):
        await ctx.respond("Bot is here!", ephemeral=True)

    @discord.slash_command(description="Show the bot's terminal log", debug_guilds=[576380164250927124])
    @discord.default_permissions(administrator=True)
    async def log(
            self,
            ctx: discord.ApplicationContext,
            lines_per_page: discord.Option(
                int,
                "Lines per page",
                required=False,
                default=DEFAULT_LINES_PER_PAGE,
                choices=LINES_PER_PAGE_OPTIONS,
            ) = DEFAULT_LINES_PER_PAGE,
    ):
        await ctx.defer(ephemeral=True)
        view = LogView(ctx, LOG_PATH, lines_per_page=lines_per_page)
        await ctx.followup.send(embed=view.build_embed(), view=view, ephemeral=True)


def setup(bot):
    bot.add_cog(DevelopmentCog(bot))
