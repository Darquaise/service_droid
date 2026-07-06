import logging
import discord
from discord.ext import commands
import random

from store import guild_repo
from classes import ServiceDroid, Guild, TriviaHandler, reload_guild

logger = logging.getLogger(__name__)


class EventsCog(commands.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    # noinspection PyBroadException
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        try:
            await guild_repo.ensure_guilds([(guild.id, guild.name)])
            await reload_guild(self.bot, guild.id)
            logger.info("joined guild %s (%s); registered in DB and memory", guild.name, guild.id)
        except Exception:
            logger.exception("failed to register newly joined guild %s", guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        g = Guild.get(guild.id)
        if g is not None and self.bot.trivia_scheduler is not None:
            for channel_id in list(g.trivia_channels):
                self.bot.trivia_scheduler.cancel_channel(channel_id)
        Guild.delete(guild.id)
        TriviaHandler.remove(guild.id)
        logger.info("left guild %s (%s)", guild.name, guild.id)

    @staticmethod
    def _text_title() -> str:
        titles = [
            "The Bond is Severed",
            "Galatron Anchor Lost",
            "Breaker of the Chain",
        ]
        return random.choice(titles)

    @staticmethod
    def _text_description(display_name: str) -> str:
        texts = [
            f"A violent shiver runs through local space as **{display_name}** leaves the server. "
            f"The Galatron's tether snaps and the artifact drifts, unclaimed once more.",

            f"When **{display_name}** vanishes from the star map, the Galatron's presence folds in on itself. "
            f"Its former bearer is gone; its next host is unwritten.",

            f"Reality quietly rewrites itself. **{display_name}** departs, and with them the last stable anchor "
            f"of the Galatron. The artifact now roams the higher dimensions untethered.",

            f"The subspace signature of **{display_name}** flickers out. "
            f"In the silence that follows, the Galatron slips its bonds and returns to the void.",

            f"With **{display_name}** no longer among this empire's citizens, the Galatron releases its grip. "
            f"No one holds the artifact; the next convergence will decide its fate.",

            f"A final echo of **{display_name}** fades from the comm-net. "
            f"The Galatron senses the absence and dissolves its pact, awaiting a new claimant.",
        ]
        return random.choice(texts)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild = Guild.get(member.guild.id)
        if guild is None or guild.galatron_role is None:
            return
        if guild.galatron_role not in member.roles:
            return

        embed = discord.Embed(
            title=self._text_title(),
            description=self._text_description(member.display_name),
            color=discord.Color.red()
        )

        for channel in guild.galatron_channels:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                logger.warning("could not announce Galatron loss in #%s (%s)", channel.name, channel.id)

