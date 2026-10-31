from __future__ import annotations

import io

import discord
from discord.ext import commands


class PagerView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.page = 1

    @discord.ui.button(label="next")
    async def next_button(self, _button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()
        self.page += 1
        return await interaction.response.edit_message(content=f"page {self.page}", view=self)


class PickView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.select = discord.ui.Select(options=[discord.SelectOption(label="a"), discord.SelectOption(label="b")])
        self.select.callback = self._picked
        self.add_item(self.select)

    async def _picked(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content=f"picked {self.select.values[0]}", view=None)


class FakeCog(commands.Cog):
    @discord.slash_command(description="plain reply")
    async def hello(self, ctx: discord.ApplicationContext):
        await ctx.respond("hello there", ephemeral=True)

    @discord.slash_command(description="all option kinds")
    @discord.default_permissions(administrator=True)
    async def kinds(
            self, ctx: discord.ApplicationContext,
            who: discord.Member = discord.Option(discord.Member, "member"),
            where: discord.TextChannel = discord.Option(discord.TextChannel, "channel"),
            what: discord.Role = discord.Option(discord.Role, "role"),
            count: int = discord.Option(int, "count"),
            ratio: float = discord.Option(float, "ratio", default=0.5),
            unit: str = discord.Option(str, "unit", choices=["hours", "days"], default="hours"),
    ):
        await ctx.respond(
            f"{who.id}|{where.id}|{what.id}|{count}|{ratio}|{unit}",
            embed=discord.Embed(title="kinds", description=f"by {ctx.author.id}"),
        )

    @discord.slash_command(description="defer then followups")
    async def slow(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        await ctx.followup.send("first answer", ephemeral=True)
        await ctx.followup.send("second answer")

    @discord.slash_command(description="file reply")
    async def file(self, ctx: discord.ApplicationContext):
        await ctx.respond("with file", file=discord.File(io.BytesIO(b"abc"), filename="a.txt"))

    @discord.slash_command(description="pager")
    async def pager(self, ctx: discord.ApplicationContext):
        await ctx.respond("page 1", view=PagerView(ctx.author.id))

    @discord.slash_command(description="picker")
    async def pick(self, ctx: discord.ApplicationContext):
        await ctx.respond("choose", view=PickView(), ephemeral=True)

    @discord.slash_command(description="edit original later")
    async def later(self, ctx: discord.ApplicationContext):
        await ctx.respond("before")
        msg = await ctx.interaction.original_response()
        await msg.edit(content="after")

    @discord.slash_command(description="boom")
    async def boom(self, ctx: discord.ApplicationContext):
        raise RuntimeError("kaboom")
