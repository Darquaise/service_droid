import logging

import discord
from discord.ext import commands

from classes import ServiceDroid

logger = logging.getLogger("service_droid.commands")


class LoggingCog(commands.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @staticmethod
    def _channel_name(ctx) -> str:
        return getattr(ctx.channel, "name", None) or str(getattr(ctx, "channel_id", "?"))

    @commands.Cog.listener()
    async def on_application_command_completion(self, ctx):
        opts = {
            o["name"]: o.get("value")
            for o in (ctx.interaction.data.get("options") or [])
        }
        logger.info(
            "cmd /%s by %s(%s) in %s/#%s opts=%s",
            ctx.command.qualified_name, ctx.user, ctx.user.id,
            ctx.guild, self._channel_name(ctx), opts,
        )

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx, error):
        logger.exception(
            "cmd /%s by %s failed: %s",
            getattr(ctx.command, "qualified_name", "?"), ctx.user, error,
            exc_info=error,
        )

        message = "Something went wrong while running this command."
        try:
            if ctx.interaction.response.is_done():
                await ctx.followup.send(message, ephemeral=True)
            else:
                await ctx.respond(message, ephemeral=True)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        logger.info(
            "cmd !%s by %s(%s) in %s/#%s",
            ctx.command.qualified_name, ctx.author, ctx.author.id,
            ctx.guild, self._channel_name(ctx),
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        logger.exception(
            "cmd !%s by %s failed: %s",
            getattr(ctx.command, "qualified_name", "?"), ctx.author, error,
            exc_info=error,
        )
