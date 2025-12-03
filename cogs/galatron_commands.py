import discord
from discord.ext import commands
import math
import random
from datetime import datetime, timedelta

from classes import ApplicationContext, ServiceDroid, GalatronStatsView
from converters.time import td2text_long


def binom_p(n, p, k):
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
            "The cosmic energies remain still for another <t:{ts}:R>. You have already challenged the Galatron recently."
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
    def success_bearer_line(user_mention: str) -> str:
        texts = [
            f"{user_mention} is now the bearer of the Galatron.",
            f"The Galatron threads itself into {user_mention}'s timeline.",
            f"From this moment on, {user_mention} carries the weight of the Galatron.",
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


class GalatronCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @staticmethod
    def _generate_leaderboard_embed(title, leaderboard) -> discord.Embed:
        lines = []
        for rank, (member, duration, amount) in enumerate(leaderboard[:10], start=1):
            lines.append(f"**{rank}.** {member.mention} ({amount}x) – {td2text_long(duration)}")

        return discord.Embed(
            title=title,
            description="\n".join(lines),
            color=discord.Color.purple()
        )

    async def get_galatron(self, ctx: ApplicationContext):
        if not ctx.galatron.role:
            return await ctx.respond("This feature hasn't been set up by your admins yet.")

        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                TextGenerator.wrong_channel(),
                ephemeral=True
            )

        member_id = ctx.author.id

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

        ctx.g.galatron_last_used[member_id] = datetime.now().replace(microsecond=0)

        if member_id not in ctx.g.galatron_total_times_used:
            ctx.g.galatron_total_times_used[member_id] = 0
        ctx.g.galatron_total_times_used[member_id] += 1

        old_owner = ctx.galatron.current_owner
        roll = random.random()

        if roll < ctx.g.galatron_chance:
            ctx.g.galatron_history.add_entry(ctx.author)
            self.bot.settings.update_guilds()

            if old_owner:
                await old_owner.remove_roles(ctx.galatron.role, reason="Galatron lost")

            await ctx.author.add_roles(ctx.galatron.role, reason="Galatron claimed")

            flavour = TextGenerator.success_text_main()
            bearer_line = TextGenerator.success_bearer_line(ctx.author.mention)

            if old_owner:
                extra = " " + TextGenerator.success_old_owner_line(old_owner.mention)
            else:
                extra = ""

            embed = discord.Embed(
                title=TextGenerator.title_awaken(),
                description=f"{flavour}\n\n{bearer_line}{extra}",
                color=discord.Color.gold()
            )
            return await ctx.respond(embed=embed)
        else:
            self.bot.settings.update_guilds()
            flavour = TextGenerator.fail_text_main()
            if old_owner:
                owner_line = " " + TextGenerator.fail_owner_bound(old_owner.mention)
            else:
                owner_line = " " + TextGenerator.fail_ownerless()

            embed = discord.Embed(
                title=TextGenerator.title_fail(),
                description=flavour + owner_line,
                color=discord.Color.dark_gray()
            )
            return await ctx.respond(embed=embed)

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

        leaderboard = sorted(ctx.g.galatron_history.calculate_leaderboard(), key=lambda x: x[1], reverse=True)

        if not leaderboard:
            return await ctx.respond(TextGenerator.no_leaderboard_entries())

        title = "Galatron Leaderboard – All-Time"
        return await ctx.respond(embed=self._generate_leaderboard_embed(title, leaderboard))

    @discord.slash_command()
    async def galatron_stats(self, ctx: ApplicationContext):
        if not ctx.galatron.is_galatron_channel:
            return await ctx.respond(
                TextGenerator.wrong_channel(),
                ephemeral=True
            )

        leaderboard_by_id = {
            int(member.id): (member, total_duration, total_got)
            for member, total_duration, total_got in ctx.g.galatron_history.calculate_leaderboard()
        }

        stats: list[tuple[discord.Member, int, int, timedelta]] = []
        for member_id, total_uses in ctx.g.galatron_total_times_used.items():
            if member_id in leaderboard_by_id.keys():
                member, total_duration, total_got = leaderboard_by_id[member_id]
            else:
                member = ctx.guild.get_member(member_id)
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
        total_uses = sum(ctx.g.galatron_total_times_used.values())  # 300
        total_received = len(ctx.g.galatron_history.history)  # 1

        percent_gotten = total_received / total_uses * 100 if total_received > 0 else 0

        cumulative_chance = 1 - sum(
            [binom_p(total_uses + 1, ctx.g.galatron_chance, k) for k in range(total_received + 1)])
        exact_chance = binom_p(total_uses + 1, ctx.g.galatron_chance, total_received + 1)

        embed = discord.Embed(
            title="Galatron Stats Total",
            description=f"**Total uses:** {total_uses} (by {individual_users} individuals)\n"
                        f"**Total received:** {total_received} ({round(percent_gotten, 2)}%)\n"
                        f"**Cumulative chance:** {round(cumulative_chance * 100, 2)}% [*](https://onlinestatbook.com/2/probability/binomial.html)\n"
                        f"**Exact chance:** {round(exact_chance * 100, 2)}%",
        )

        return await ctx.respond(embed=embed)


def setup(bot: ServiceDroid):
    bot.add_cog(GalatronCog(bot))
