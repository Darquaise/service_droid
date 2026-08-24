import asyncio
import discord
from discord.ext import commands
import random
from typing import Iterable
from datetime import timedelta

from classes import (
    ApplicationContext, ServiceDroid, GalatronStatsView, GalatronLeaderboardView, role_assignment_error, notify_owner
)
from classes.galatron_leaderboard_view import PRIME_DELAY


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


class TextGenerator:
    @staticmethod
    def fail_text_main() -> str:
        texts = [
            "The hyperdimensional lattice shudders for a moment, but the Galatron remains out of reach.",
            "Your fleet pierces the shimmering veil, but finds only cold interstellar dust.",
            "The cube of reality turns – but not in your favor.",
            "A distant echo answers your call, yet the Galatron stays hidden in higher dimensions.",
            "Sensors spike and then fall silent. Whatever brushed against your reality was not the Galatron.",
            "For a heartbeat the stars rearrange themselves, mocking your attempt to grasp the Galatron.",
            "A thousand possible timelines flare and collapse; in none of them do you claim the Galatron… yet.",
            "Space-time ripples around you, then smooths out again, as if amused by your ambition.",
        ]
        return random.choice(texts)

    @staticmethod
    def success_text_main() -> str:
        texts = [
            "Reality buckles. The Galatron materializes before you.",
            "An unnatural radiance cuts through the dark. The Galatron is now yours.",
            "The galaxy holds its breath as the Galatron falls into your hands.",
            "The veils between dimensions tear – you are now the bearer of the Galatron.",
            "For a moment, every star in the sky turns to face you. The Galatron has chosen its vessel.",
            "Causality fractures into a thousand shards, and in every reflection you are holding the Galatron.",
            "Ancient subspace signals align into a single wordless verdict: you are worthy.",
            "The void roars in silent approval as the Galatron locks itself into your timeline.",
        ]
        return random.choice(texts)

    @staticmethod
    def wrong_channel() -> str:
        texts = [
            "The fabric of reality is too unstable here. Use this command in the designated Galatron channel.",
            "The Galatron does not answer from this location. Perform the ritual in the proper channel.",
            "Subspace interference is too high in this channel. Switch to the Galatron channel and try again.",
        ]
        return random.choice(texts)

    @staticmethod
    def cooldown(next_allowed_ts: int) -> str:
        templates = [
            "The cosmic energies remain still. You have already challenged the Galatron recently, try again <t:{ts}:R>.",
            "You may attempt another contact <t:{ts}:R>.",
            "Reality refuses to twist for you again so soon. The next alignment window opens <t:{ts}:R>.",
            "The Galatron ignores repeated calls. Try again when the timelines realign <t:{ts}:R>.",
        ]
        return random.choice(templates).format(ts=next_allowed_ts)

    @staticmethod
    def already_owner() -> str:
        texts = [
            "You already carry the Galatron; reality will not forge a second copy for you.",
            "The Galatron is already bound to you. Even it respects conservation of artifacts.",
            "You feel the weight of the Galatron already; there is nothing more for reality to grant you.",
        ]
        return random.choice(texts)

    @staticmethod
    def title_awaken() -> str:
        titles = [
            "The Galatron Awakens",
            "Ascension of the Galatron",
            "Resonance of the Galatron",
        ]
        return random.choice(titles)

    @staticmethod
    def title_fail() -> str:
        titles = [
            "Empty Resonance",
            "Failed Convergence",
            "Silence in the Void",
        ]
        return random.choice(titles)

    @staticmethod
    def success_bearer_line() -> str:
        texts = [
            "You are now the bearer of the Galatron.",
            "The Galatron threads itself into your timeline.",
            "From this moment on, you carry the weight of the Galatron.",
        ]
        return random.choice(texts)

    @staticmethod
    def success_old_owner_line(old_owner_mention: str) -> str:
        texts = [
            f"The dominion of {old_owner_mention} shatters as the artifact slips from their grasp.",
            f"Reality pries the Galatron from {old_owner_mention}'s hands and rewrites the balance of power.",
            f"{old_owner_mention} feels the impossible weight vanish, their claim erased in an instant.",
        ]
        return random.choice(texts)

    @staticmethod
    def fail_owner_bound(owner_mention: str) -> str:
        texts = [
            f"The Galatron remains bound to {owner_mention}, its power refusing to change hands.",
            f"The artifact flickers, then settles back into the grasp of {owner_mention}.",
            f"For now, {owner_mention} retains their grip on the Galatron's impossible geometry.",
        ]
        return random.choice(texts)

    @staticmethod
    def fail_ownerless() -> str:
        texts = [
            "The Galatron drifts masterless in hyperdimensional space, ignoring your plea.",
            "Somewhere beyond ordinary space, the Galatron spins in solitude, indifferent to your attempt.",
            "The artifact hangs in the void, unattached, awaiting a bearer that is not you.",
        ]
        return random.choice(texts)

    @staticmethod
    def title_status() -> str:
        titles = [
            "Galatron Status",
            "Current State of the Galatron",
            "Galatron Signal Report",
        ]
        return random.choice(titles)

    @staticmethod
    def status_bound(user_mention: str) -> str:
        texts = [
            f"The Galatron currently rests in the hands of {user_mention}.",
            f"Subspace telemetry confirms {user_mention} as the present bearer of the Galatron.",
            f"All readings point to {user_mention} as the artifact's current anchor.",
        ]
        return random.choice(texts)

    @staticmethod
    def status_unbound() -> str:
        texts = [
            "The Galatron is currently not bound to any mortal mind or empire.",
            "No active bearer detected; the Galatron appears unbound and drifting.",
            "The artifact's signature is diffuse. It acknowledges no master at this time.",
        ]
        return random.choice(texts)

    @staticmethod
    def no_leaderboard_entries() -> str:
        texts = [
            "There are no entries in the Galatron chronicle yet.",
            "The chronicle pages are blank; no one has held the Galatron long enough to be recorded.",
            "History has not yet been written. The Galatron awaits its first documented bearer.",
        ]
        return random.choice(texts)

    @staticmethod
    def no_trys_yet() -> str:
        texts = [
            "Noone has ever tried achieving the Galatron."
        ]
        return random.choice(texts)

    @staticmethod
    def short_success(old_owner_mention: str | None = None) -> str:
        if old_owner_mention:
            texts = [
                f"You now bear the Galatron — {old_owner_mention} feels it slip away.",
                f"The Galatron answers you. {old_owner_mention} is left empty-handed.",
                f"Reality realigns. The artifact passes from {old_owner_mention} to you.",
                f"You claim the Galatron from {old_owner_mention}.",
                f"The Galatron unbinds from {old_owner_mention} and threads into your fate.",
            ]
        else:
            texts = [
                "You now bear the Galatron.",
                "The Galatron answers — and chooses you.",
                "Reality realigns. The artifact is yours.",
                "The timelines settle on you as bearer.",
                "The Galatron threads itself into your fate.",
            ]
        return random.choice(texts)

    @staticmethod
    def short_fail() -> str:
        texts = [
            "The Galatron eludes you.",
            "You grasp only void.",
            "Subspace stays silent for you.",
            "The artifact ignores you.",
            "You reach into the dark — nothing answers.",
        ]
        return random.choice(texts)


class GalatronCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @staticmethod
    async def get_galatron(ctx: ApplicationContext):
        if not ctx.galatron.role:
            return await ctx.respond("This feature hasn't been set up by your admins yet.")

        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                TextGenerator.wrong_channel(),
                ephemeral=True
            )

        next_allowed = ctx.galatron.is_on_cooldown
        if next_allowed:
            return await ctx.respond(
                TextGenerator.cooldown(int(next_allowed.timestamp())),
                ephemeral=True
            )

        if ctx.galatron.is_current_owner:
            return await ctx.respond(
                TextGenerator.already_owner(),
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
            return await ctx.respond(
                "The Galatron ritual is unstable — the server admins have been notified to fix "
                "my permissions. Try again once it's sorted.",
                ephemeral=True,
            )

        old_owner = ctx.galatron.current_owner
        roll = random.random()

        if roll < ctx.g.galatron_chance:
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
                return await ctx.respond(
                    "Reality resisted — I couldn't bind the Galatron. The server admins have "
                    "been notified.",
                    ephemeral=True,
                )

            await ctx.g.galatron_record_attempt(ctx.author, won=True)

            flavour = TextGenerator.success_text_main()
            bearer_line = TextGenerator.success_bearer_line()
            extra = " " + TextGenerator.success_old_owner_line(old_owner.mention) if old_owner else ""

            await ctx.respond(
                f"-# {TextGenerator.short_success(old_owner.mention if old_owner else None)}"
            )
            return await ctx.followup.send(
                f"**{TextGenerator.title_awaken()}**\n{flavour}\n{bearer_line}{extra}",
                ephemeral=True,
            )
        else:
            await ctx.g.galatron_record_attempt(ctx.author, won=False)

            flavour = TextGenerator.fail_text_main()
            if old_owner:
                owner_line = " " + TextGenerator.fail_owner_bound(old_owner.mention)
            else:
                owner_line = " " + TextGenerator.fail_ownerless()

            await ctx.respond(f"-# {TextGenerator.short_fail()}")
            return await ctx.followup.send(
                f"**{TextGenerator.title_fail()}**\n{flavour}{owner_line}",
                ephemeral=True,
            )

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
                TextGenerator.wrong_channel(),
                ephemeral=True
            )

        current = ctx.galatron.current_owner
        if current:
            desc = TextGenerator.status_bound(current.mention)
        else:
            desc = TextGenerator.status_unbound()

        embed = discord.Embed(
            title=TextGenerator.title_status(),
            description=desc,
            color=discord.Color.blue()
        )
        return await ctx.respond(embed=embed)

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
                TextGenerator.wrong_channel(),
                ephemeral=True
            )

        leaderboard = sorted(await ctx.g.galatron_log.calculate_leaderboard(), key=lambda x: x[1], reverse=True)

        if not leaderboard:
            return await ctx.respond(TextGenerator.no_leaderboard_entries())

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
                TextGenerator.wrong_channel(),
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
                TextGenerator.wrong_channel(),
                ephemeral=True
            )

        log = ctx.g.galatron_log
        if log.total_attempts == 0:
            return await ctx.respond(
                TextGenerator.no_trys_yet(),
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
