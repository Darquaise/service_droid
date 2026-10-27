import asyncio
import discord
from discord.ext import commands
import random
from pathlib import Path
from typing import Iterable
from datetime import timedelta

from classes import (
    ApplicationContext, ServiceDroid, GalatronStatsView, GalatronLeaderboardView, role_assignment_error, notify_owner
)
from classes.galatron_leaderboard_view import PRIME_DELAY
from classes import galatron_text as text

GALATRON_IMAGE = Path(__file__).resolve().parent.parent / "assets" / "galatron.png"


def binomial_pmf(n: int, p: float, k_max: int) -> list[float]:
    """P(exactly k wins) for k = 0…k_max out of n attempts at chance p, built from
    P(k-1) so no huge binomial coefficient is ever materialised."""
    top = min(n, k_max)
    if p <= 0:
        return [1.0] + [0.0] * top
    if p >= 1:
        return [0.0] * top + ([1.0] if n <= k_max else [0.0])
    pmf = [(1 - p) ** n]
    for k in range(1, top + 1):
        pmf.append(pmf[-1] * (n - k + 1) / k * p / (1 - p))
    return pmf


def win_count_pmf(groups: Iterable[tuple[float, int]], k_max: int) -> list[float]:
    """P(exactly k wins) for k = 0…k_max over attempts made at differing chances.

    Each group is ``(chance, attempts)``; with a single group this is the plain binomial
    distribution, with several it is their convolution (Poisson binomial)."""
    pmf = [1.0]
    for p, n in groups:
        if n <= 0:
            continue
        group = binomial_pmf(n, p, k_max)
        combined = [0.0] * (min(len(pmf) + len(group) - 2, k_max) + 1)
        for i, left in enumerate(pmf):
            if left == 0.0:
                continue
            for j, right in enumerate(group):
                if i + j > k_max:
                    break
                combined[i + j] += left * right
        pmf = combined
    return pmf


class GalatronCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @staticmethod
    async def get_galatron(ctx: ApplicationContext):
        if not ctx.galatron.role:
            return await ctx.respond("This feature hasn't been set up by your admins yet.")

        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                text.wrong_channel(ctx.guild.id, ctx.g.galatron_register),
                ephemeral=True
            )

        next_allowed = ctx.galatron.is_on_cooldown
        if next_allowed:
            return await ctx.respond(
                text.cooldown(ctx.guild.id, ctx.g.galatron_register, int(next_allowed.timestamp())),
                ephemeral=True
            )

        if ctx.galatron.is_current_owner:
            return await ctx.respond(
                text.already_owner(ctx.guild.id, ctx.g.galatron_register),
                ephemeral=True
            )

        # Bail out before consuming the attempt if we couldn't hand out the role on a win.
        role_err = role_assignment_error(ctx.guild, ctx.galatron.role)
        if role_err:
            await notify_owner(
                ctx.guild,
                f"The Galatron hunt is broken: {role_err}\n"
                f"Attempts are paused until this is fixed.",
            )
            return await ctx.respond(text.suspended(ctx.guild.id), ephemeral=True)

        # Built before the attempt is recorded, so the log still holds only past attempts.
        attempt = text.build_context(ctx.g.galatron_log, ctx.author.id)
        old_owner = attempt.old_owner
        won = random.random() < ctx.g.galatron_chance

        if won:
            try:
                if old_owner:
                    await old_owner.remove_roles(ctx.galatron.role, reason="Galatron lost")
                await ctx.author.add_roles(ctx.galatron.role, reason="Galatron claimed")
            except discord.Forbidden:
                await notify_owner(
                    ctx.guild,
                    f"I lost permission to assign {ctx.galatron.role.mention} mid-hunt "
                    f"(is my role still above it?). The last attempt couldn't be completed.",
                )
                return await ctx.respond(text.transfer_failed(ctx.guild.id), ephemeral=True)

        # Read before recording: a win rerolls the register, but is itself told in the old one.
        register = ctx.g.galatron_register
        await ctx.g.galatron_record_attempt(ctx.author, won=won)
        composed = text.compose_attempt(attempt, won, ctx.guild.id, register)

        if not won:
            # The channel only gets the one-liner, the write-up stays with whoever dug.
            await ctx.respond(f"-# {composed.short}")
            return await ctx.followup.send(composed.body, ephemeral=True)

        # A win is rare and worth the whole channel seeing it, artwork included.
        if not ctx.channel.permissions_for(ctx.guild.me).attach_files:
            await notify_owner(
                ctx.guild,
                f"I'm missing **Attach Files** in {ctx.channel.mention}, so Galatron wins are "
                f"announced without the artwork.",
            )
            return await ctx.respond(composed.body)
        return await ctx.respond(composed.body, file=discord.File(GALATRON_IMAGE))

    @discord.slash_command(
        name="attempt_galatron",
        description="Reach into twisted reality and attempt to claim the cosmic artifact known as the Galatron."
    )
    async def command_attempt_galatron(self, ctx: ApplicationContext):
        await self.get_galatron(ctx)

    @discord.slash_command(
        name="galatron_attempt",
        description="Reach into twisted reality and attempt to claim the cosmic artifact known as the Galatron."
    )
    async def command_galatron_attempt(self, ctx: ApplicationContext):
        await self.get_galatron(ctx)

    @staticmethod
    async def locate_galatron(ctx: ApplicationContext):
        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                text.wrong_channel(ctx.guild.id, ctx.g.galatron_register),
                ephemeral=True
            )

        # Plain text since a mention inside an embed stays unresolved for viewers who don't have that member cached
        return await ctx.respond(
            f"**{text.status_title(ctx.guild.id, ctx.g.galatron_register)}**\n"
            f"{text.status(ctx.guild.id, ctx.g.galatron_register, ctx.galatron.current_owner)}",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @discord.slash_command(
        name="locate_galatron",
        description="Reveal the current location of the Galatron and its chosen bearer."
    )
    async def command_locate_galatron(self, ctx: ApplicationContext):
        await self.locate_galatron(ctx)

    @discord.slash_command(
        name="galatron_locate",
        description="Reveal the current location of the Galatron and its chosen bearer."
    )
    async def command_galatron_locate(self, ctx: ApplicationContext):
        await self.locate_galatron(ctx)

    @discord.slash_command(description="Show the all-time leaderboard of Galatron bearers.")
    async def galatron_leaderboard(self, ctx: ApplicationContext):
        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                text.wrong_channel(ctx.guild.id, ctx.g.galatron_register),
                ephemeral=True
            )

        leaderboard = sorted(await ctx.g.galatron_log.calculate_leaderboard(), key=lambda x: x[1], reverse=True)

        if not leaderboard:
            return await ctx.respond(text.no_leaderboard_entries(ctx.guild.id, ctx.g.galatron_register))

        title = "Galatron Leaderboard – All-Time"
        view = GalatronLeaderboardView(ctx, leaderboard, title)
        content = view.build_content(view.current_page)
        view.primed_pages.add(view.current_page)

        if content:
            await ctx.respond(
                content=content,
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            view.message = await ctx.interaction.original_response()
            await asyncio.sleep(PRIME_DELAY)
            try:
                await view.message.edit(
                    content="",
                    embeds=view.build_embeds(view.current_page),
                    view=view,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                pass
        else:
            await ctx.respond(
                embeds=view.build_embeds(view.current_page),
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            view.message = await ctx.interaction.original_response()
        return None

    @discord.slash_command()
    async def galatron_stats(self, ctx: ApplicationContext):
        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                text.wrong_channel(ctx.guild.id, ctx.g.galatron_register),
                ephemeral=True
            )

        leaderboard_by_id = {
            int(member.id): (member, total_duration, total_got)
            for member, total_duration, total_got in await ctx.g.galatron_log.calculate_leaderboard()
        }

        stats: list[tuple[discord.Member, int, int, timedelta]] = []
        for member_id, total_uses in ctx.g.galatron_log.totals.items():
            if member_id in leaderboard_by_id.keys():
                member, total_duration, total_got = leaderboard_by_id[member_id]
            else:
                member = ctx.guild.get_member(member_id)
                if not member:
                    continue
                total_got = 0
                total_duration = timedelta()

            stats.append((member, total_uses, total_got, total_duration))

        stats.sort(key=lambda x: x[1], reverse=True)

        view = GalatronStatsView(ctx, stats)
        embed = view.build_embed(0)
        return await ctx.respond(embed=embed, view=view)

    @discord.slash_command()
    async def galatron_stats_total(self, ctx: ApplicationContext):
        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                text.wrong_channel(ctx.guild.id, ctx.g.galatron_register),
                ephemeral=True
            )

        log = ctx.g.galatron_log
        if log.total_attempts == 0:
            return await ctx.respond(
                text.no_attempts_yet(ctx.guild.id, ctx.g.galatron_register),
            )

        individual_users = len(log.totals)
        total_uses = log.total_attempts
        total_received = len(log.wins)

        # Each attempt counts with the chance that was in force when it was made, so a
        # chance that changed over time doesn't distort the expectation.
        groups = sorted(ctx.g.galatron_attempts_by_chance().items())
        expected = sum(p * n for p, n in groups)

        pmf = win_count_pmf(groups, total_received)
        luck_percentile = 1 - sum(pmf[:total_received])  # P(at least this many wins)
        low_tail = sum(pmf[:total_received + 1])  # P(at most this many wins)

        empirical_rate = total_received / total_uses * 100

        if expected > 0:
            luck_factor_text = f"{total_received / expected:.2f}× the average"
        else:
            luck_factor_text = "-"

        description = (
            f"**Total uses:** {total_uses} (by {individual_users} individuals)\n"
            f"**Total received:** {total_received} ({empirical_rate:.2f}%)\n"
            f"**Server chance:** {ctx.g.galatron_chance * 100}%\n"
        )
        if len(groups) > 1:
            spread = ", ".join(f"{p * 100:g}% ({n}×)" for p, n in groups)
            description += f"**Chances these attempts were made under:** {spread}\n"
        description += (
            f"**Expected:** {expected:.2f} ({luck_factor_text})\n"
            f"**P(at least this lucky):** {luck_percentile * 100:.2f}% "
        )

        if min(luck_percentile, low_tail) < 0.01:
            description += "\n\n-# This result is statistically extreme."

        embed = discord.Embed(title="Galatron Stats Total", description=description)

        return await ctx.respond(embed=embed)
