from typing import Awaitable, Callable

import discord
from discord.ext import commands

from classes import (
    ServiceDroid,
    ApplicationContext,
    TriviaHandler,
    TriviaChannelConfig,
    TriviaQuestionPaginatorView,
    trivia_modes, TriviaScheduler,
)

CRON_HELP = (
    "Schedule must be a valid cron expression (5 fields: `min hour day month weekday`).\n"
    "Examples:\n"
    "• `0 20 * * *` — every day at 20:00\n"
    "• `*/30 * * * *` — every 30 minutes\n"
    "• `0 18 * * 5` — every Friday at 18:00"
)

OnSelectCallback = Callable[[discord.Interaction, str], Awaitable[None]]


def _refresh_scheduler(bot: ServiceDroid, channel_id: int, config: TriviaChannelConfig | None) -> None:
    scheduler: TriviaScheduler = getattr(bot, "trivia_scheduler")
    if scheduler is None:
        return
    if config is None:
        scheduler.cancel_channel(channel_id)
    else:
        scheduler.schedule_channel(channel_id, config)


MODE_CHOICES = [
    discord.OptionChoice(name=trivia_modes.MODE_DISPLAY[m], value=m)
    for m in trivia_modes.SELECTABLE_MODES
]
ORDER_CHOICES = [
    discord.OptionChoice(name=trivia_modes.ORDER_DISPLAY[o], value=o)
    for o in trivia_modes.ALL_ORDERS
]


class TriviaListSelectView(discord.ui.View):
    def __init__(
            self, ctx: ApplicationContext, list_names: list[str], on_select: OnSelectCallback,
            placeholder: str = "Pick a list...", timeout: float = 120,
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.on_select = on_select

        options = [discord.SelectOption(label=name, value=name) for name in list_names]
        self.select = discord.ui.Select(
            placeholder=placeholder, min_values=1, max_values=1, options=options
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()

        list_name = self.select.values[0]
        for child in self.children:
            child.disabled = True

        await self.on_select(interaction, list_name)


async def _prompt_list_select(
        ctx: ApplicationContext, on_select: OnSelectCallback,
        prompt: str = "Pick a list:",
) -> None:
    handler = TriviaHandler.get_or_create(ctx.guild)
    list_names = handler.get_list_names()
    if not list_names:
        await ctx.respond("There are no trivia lists yet.", ephemeral=True)
        return

    view = TriviaListSelectView(ctx, list_names, on_select)
    await ctx.respond(prompt, view=view, ephemeral=True)


class TriviaSettingsCog(commands.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    # ---------------------------------------------------------------------
    # List management (per-guild trivia file)
    # ---------------------------------------------------------------------

    @discord.slash_command(description="Show all trivia lists with their question count.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_list(self, ctx: ApplicationContext):
        handler = TriviaHandler.get_or_create(ctx.guild)
        if not handler.lists:
            return await ctx.respond("There are no trivia lists yet.", ephemeral=True)

        lines = [f"• **{name}** — {len(questions)} questions" for name, questions in handler.lists.items()]
        embed = discord.Embed(title="Trivia lists", description="\n".join(lines), color=0xffd700)
        return await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(description="Create a new, empty trivia list.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_list_add(self, ctx: ApplicationContext, name: str):
        handler = TriviaHandler.get_or_create(ctx.guild)
        if not handler.add_list(name):
            return await ctx.respond(f"List **{name}** already exists.", ephemeral=True)
        self.bot.settings.update_trivia(ctx.guild.id)
        return await ctx.respond(f"List **{name}** has been created.", ephemeral=True)

    @discord.slash_command(description="Remove a trivia list.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_list_remove(self, ctx: ApplicationContext):
        handler = TriviaHandler.get_or_create(ctx.guild)

        async def on_select(interaction: discord.Interaction, list_name: str):
            guild = ctx.g
            referencing_channels = [
                cid for cid, cfg in guild.trivia_channels.items() if cfg.list_name == list_name
            ]
            if referencing_channels:
                mentions = ", ".join(f"<#{cid}>" for cid in referencing_channels)
                return await interaction.response.edit_message(
                    content=(
                        f"List **{list_name}** is still being used by: {mentions}.\n"
                        f"Detach it first with `/setting_trivia_reset_channel`."
                    ),
                    view=None,
                )

            handler.remove_list(list_name)
            self.bot.settings.update_trivia(ctx.guild.id)
            await interaction.response.edit_message(
                content=f"List **{list_name}** has been deleted.", view=None
            )

        await _prompt_list_select(ctx, on_select, "Which list should be removed?")

    @discord.slash_command(description="Show all questions of a trivia list.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_list_show(self, ctx: ApplicationContext):
        handler = TriviaHandler.get_or_create(ctx.guild)

        async def on_select(interaction: discord.Interaction, list_name: str):
            questions = handler.lists[list_name]
            view = TriviaQuestionPaginatorView(ctx, list_name, questions)
            embed = view.build_embed(0)
            if not questions:
                await interaction.response.edit_message(content=None, embed=embed, view=None)
                return
            await interaction.response.edit_message(content=None, embed=embed, view=view)

        await _prompt_list_select(ctx, on_select, "Which list should be shown?")

    @discord.slash_command(description="Add a new question to a list.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_add(
            self, ctx: ApplicationContext,
            title: str, question: str, answer: str, answer_context: str = ""
    ):
        handler = TriviaHandler.get_or_create(ctx.guild)

        async def on_select(interaction: discord.Interaction, list_name: str):
            new_q = handler.add_question(list_name, title, [question], answer, answer_context)
            self.bot.settings.update_trivia(ctx.guild.id)
            await interaction.response.edit_message(
                content=f"Question `{new_q.id}` added to list **{list_name}**.",
                view=None,
            )

        await _prompt_list_select(ctx, on_select, "Which list should the question be added to?")

    @discord.slash_command(description="Remove a question from a list.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_remove(self, ctx: ApplicationContext, trivia_id: int):
        handler = TriviaHandler.get_or_create(ctx.guild)

        async def on_select(interaction: discord.Interaction, list_name: str):
            if not handler.remove_question(list_name, trivia_id):
                return await interaction.response.edit_message(
                    content=f"There is no question with ID `{trivia_id}` in **{list_name}**.",
                    view=None,
                )
            self.bot.settings.update_trivia(ctx.guild.id)
            await interaction.response.edit_message(
                content=f"Question `{trivia_id}` removed from list **{list_name}**.",
                view=None,
            )

        await _prompt_list_select(ctx, on_select, "Which list should the question be removed from?")

    # ---------------------------------------------------------------------
    # Channel mapping (guilds.json)
    # ---------------------------------------------------------------------

    @discord.slash_command(
        description="Bind a channel to a trivia list with its own cron schedule and response time."
    )
    @discord.default_permissions(administrator=True)
    async def setting_trivia_set_channel(
            self, ctx: ApplicationContext,
            channel: discord.TextChannel,
            schedule: discord.Option(
                str, "5-field cron expression, e.g. 0 20 * * * runs daily at 20:00"
            ),
            response: discord.Option(int, "Seconds to wait before posting the answer"),
            mode: discord.Option(
                str, "How questions are resolved", choices=MODE_CHOICES,
                default=trivia_modes.MODE_TIMED,
            ),
            order: discord.Option(
                str, "How the next question is picked", choices=ORDER_CHOICES,
                default=trivia_modes.ORDER_RANDOM,
            ),
    ):
        if not TriviaChannelConfig.is_valid_cron(schedule):
            return await ctx.respond(
                f"`{schedule}` is not a valid cron expression.\n\n{CRON_HELP}",
                ephemeral=True,
            )
        if response <= 0:
            return await ctx.respond("Response time must be greater than 0 seconds.", ephemeral=True)

        handler = TriviaHandler.get_or_create(ctx.guild)
        list_names = handler.get_list_names()
        if not list_names:
            return await ctx.respond("There are no trivia lists yet.", ephemeral=True)

        async def on_select(interaction: discord.Interaction, list_name: str):
            guild = ctx.g
            config = TriviaChannelConfig(
                channel_id=channel.id,
                list_name=list_name,
                schedule=schedule,
                response=response,
                mode=mode,
                order=order,
            )
            guild.trivia_channels[channel.id] = config
            self.bot.settings.update_guilds()
            _refresh_scheduler(self.bot, channel.id, config)
            await interaction.response.edit_message(
                content=(
                    f"{channel.mention} is now bound to list **{list_name}**.\n"
                    f"Schedule: `{schedule}` | Response: {response}s\n"
                    f"Mode: {trivia_modes.MODE_DISPLAY.get(mode, mode)} | "
                    f"Order: {trivia_modes.ORDER_DISPLAY.get(order, order)}\n"
                    f"Next: {config.next_fire_discord()}"
                ),
                embed=None,
                view=None,
            )

        view = TriviaListSelectView(ctx, list_names, on_select)
        cron_embed = discord.Embed(
            title="Cron schedule reference",
            description=CRON_HELP,
            color=0xffd700,
        )
        return await ctx.respond(
            f"Pick the list to use in {channel.mention}:",
            embed=cron_embed,
            view=view,
            ephemeral=True,
        )

    @discord.slash_command(description="Remove a channel's trivia mapping.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_reset_channel(self, ctx: ApplicationContext, channel: discord.TextChannel):
        guild = ctx.g
        if channel.id not in guild.trivia_channels:
            return await ctx.respond(
                f"{channel.mention} is not a trivia channel.", ephemeral=True
            )
        del guild.trivia_channels[channel.id]
        self.bot.settings.update_guilds()
        _refresh_scheduler(self.bot, channel.id, None)
        return await ctx.respond(
            f"Trivia mapping for {channel.mention} removed.", ephemeral=True
        )

    @discord.slash_command(description="Show all channel→list mappings.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_show_mappings(self, ctx: ApplicationContext):
        guild = ctx.g
        if not guild.trivia_channels:
            return await ctx.respond("No channel mappings have been set yet.", ephemeral=True)

        lines = []
        for cid, cfg in guild.trivia_channels.items():
            mode_name = trivia_modes.MODE_DISPLAY.get(cfg.mode, cfg.mode)
            order_name = trivia_modes.ORDER_DISPLAY.get(cfg.order, cfg.order)
            lines.append(
                f"<#{cid}> → **{cfg.list_name}**\n"
                f"   Schedule: `{cfg.schedule}` | Response: {cfg.response}s\n"
                f"   Mode: {mode_name} | Order: {order_name}\n"
                f"   Next: {cfg.next_fire_discord()}"
            )
        embed = discord.Embed(
            title="Trivia channel mappings", description="\n\n".join(lines), color=0xffd700
        )
        return await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(description="Update the schedule of an existing trivia channel.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_update_schedule(
            self, ctx: ApplicationContext, channel: discord.TextChannel, schedule: str
    ):
        guild = ctx.g
        if channel.id not in guild.trivia_channels:
            return await ctx.respond(
                f"{channel.mention} is not a trivia channel.", ephemeral=True
            )
        if not TriviaChannelConfig.is_valid_cron(schedule):
            return await ctx.respond(
                f"`{schedule}` is not a valid cron expression.\n\n{CRON_HELP}",
                ephemeral=True,
            )
        config = guild.trivia_channels[channel.id]
        config.schedule = schedule
        self.bot.settings.update_guilds()
        _refresh_scheduler(self.bot, channel.id, config)
        return await ctx.respond(
            f"Schedule for {channel.mention} is now `{schedule}`.", ephemeral=True
        )

    @discord.slash_command(description="Update the response time of an existing trivia channel.")
    @discord.default_permissions(administrator=True)
    async def setting_trivia_update_response(
            self, ctx: ApplicationContext, channel: discord.TextChannel, response: int
    ):
        guild = ctx.g
        if channel.id not in guild.trivia_channels:
            return await ctx.respond(
                f"{channel.mention} is not a trivia channel.", ephemeral=True
            )
        if response <= 0:
            return await ctx.respond("Response time must be greater than 0 seconds.", ephemeral=True)
        config = guild.trivia_channels[channel.id]
        config.response = response
        self.bot.settings.update_guilds()
        _refresh_scheduler(self.bot, channel.id, config)
        return await ctx.respond(
            f"Response time for {channel.mention} is now {response}s.", ephemeral=True
        )


def setup(bot: ServiceDroid):
    bot.add_cog(TriviaSettingsCog(bot))
