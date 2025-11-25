import discord
from discord.ext import commands
import random

from classes import ServiceDroid, Guild


class EventsCog(commands.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

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
    async def on_member_remove(self, member: discord.Member):
        guild = Guild.get(member.guild.id)
        if not guild.galatron_role in member.roles:
            return

        embed = discord.Embed(
            title=self._text_title(),
            description=self._text_description(member.display_name),
            color=discord.Color.red()
        )

        for channel in guild.galatron_channels:
            await channel.send(embed=embed)


def setup(bot: ServiceDroid):
    bot.add_cog(EventsCog(bot))
