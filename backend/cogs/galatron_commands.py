import asyncio
import discord
from discord.ext import commands
import math
import random
from datetime import timedelta

from classes import ApplicationContext, ServiceDroid, GalatronStatsView, GalatronLeaderboardView
from classes.galatron_leaderboard_view import PRIME_DELAY


def binom_p(n: int, p: float, k: int) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


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

    @staticmethod
    def title_decree() -> str:
        titles = [
            "Decree of the Galactic Custodian",
            "Mandate of the Outer Council",
            "Override from the Shroud",
            "Custodian Reallocation Order",
            "Imperial Edict — Artifact Reassignment",
            "Curator Intervention",
        ]
        return random.choice(titles)

    @staticmethod
    def admin_transfer(new_mention: str, old_mention: str | None) -> str:
        if old_mention:
            texts = [
                f"A coded signal pierces every subspace channel — its cipher older than any current empire. The Galatron is torn from {old_mention} and pressed into the hands of {new_mention}.",
                f"The Custodian speaks. Reality is overruled: {old_mention} is severed from the artifact, and {new_mention} becomes its new vessel.",
                f"Beyond the senate, beyond the council, an unseen authority moves a piece on the board. {old_mention} is dispossessed; {new_mention} now carries the Galatron.",
                f"An edict descends through the L-Gate networks. No vote was cast, no war was fought — yet {old_mention} loses the Galatron, and {new_mention} is named its bearer.",
                f"The Shroud ripples with foreign intent. {old_mention}'s claim is unwoven from the timeline; {new_mention}'s thread is bound to the artifact in its place.",
            ]
        else:
            texts = [
                f"A directive descends from beyond the galactic frontier. The unbound Galatron is forcibly tethered to {new_mention} by powers that answer to no senate.",
                f"The Custodian's voice resonates through every relay: the artifact shall drift no longer. {new_mention} is its bearer, by decree.",
                f"From outside known space, a higher authority intervenes. The Galatron, masterless until now, is bound to {new_mention}.",
                f"An ancient protocol activates without warning. The Galatron's coordinates collapse onto {new_mention}, sealing the appointment.",
            ]
        return random.choice(texts)

    @staticmethod
    def admin_transfer_same(owner_mention: str) -> str:
        texts = [
            f"The Custodian's gaze falls on {owner_mention} — and finds them already bound to the Galatron. The decree dissolves without effect.",
            f"Reality has been pre-arranged. {owner_mention} already carries the Galatron; the intervention only confirms what is.",
            f"The edict echoes through empty subspace. {owner_mention} is the bearer, was the bearer, remains the bearer.",
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

        await ctx.g.galatron_register_attempt(ctx.author)

        old_owner = ctx.galatron.current_owner
        roll = random.random()

        if roll < ctx.g.galatron_chance:
            await ctx.g.galatron_add_win(ctx.author)

            if old_owner:
                await old_owner.remove_roles(ctx.galatron.role, reason="Galatron lost")

            await ctx.author.add_roles(ctx.galatron.role, reason="Galatron claimed")

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

        leaderboard = sorted(await ctx.g.galatron_history.calculate_leaderboard(), key=lambda x: x[1], reverse=True)

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
            for member, total_duration, total_got in await ctx.g.galatron_history.calculate_leaderboard()
        }

        stats: list[tuple[discord.Member, int, int, timedelta]] = []
        for member_id, total_uses in ctx.g.galatron_total_times_used.items():
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

        if not len(ctx.g.galatron_total_times_used) > 0:
            return await ctx.respond(
                TextGenerator.no_trys_yet(),
            )

        individual_users = len(ctx.g.galatron_total_times_used)
        total_uses = sum(ctx.g.galatron_total_times_used.values())
        total_received = len(ctx.g.galatron_history.history)
        p = ctx.g.galatron_chance

        empirical_rate = total_received / total_uses * 100
        expected = p * total_uses
        luck_percentile = 1 - sum(binom_p(total_uses, p, k) for k in range(total_received))
        low_tail = 1 - luck_percentile + binom_p(total_uses, p, total_received)

        if expected > 0:
            luck_factor_text = f"{total_received / expected:.2f}× the average"
        else:
            luck_factor_text = "-"

        description = (
            f"**Total uses:** {total_uses} (by {individual_users} individuals)\n"
            f"**Total received:** {total_received} ({empirical_rate:.2f}%)\n"
            f"**Server chance:** {p * 100}%\n"
            f"**Expected:** {expected:.2f} ({luck_factor_text})\n"
            f"**P(at least this lucky):** {luck_percentile * 100:.2f}% "
        )

        if min(luck_percentile, low_tail) < 0.01:
            description += (
                "\n\n-# This result is statistically extreme under the current server chance "
                "- the chance may have been different during past attempts."
            )

        embed = discord.Embed(title="Galatron Stats Total", description=description)

        return await ctx.respond(embed=embed)
