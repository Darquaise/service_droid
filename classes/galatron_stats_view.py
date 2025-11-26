import discord
from discord.ui import View, button
import math
from datetime import timedelta

from converters import td2text
from .context import ApplicationContext

PAGE_SIZE = 20


class GalatronStatsView(View):
    def __init__(self, ctx: ApplicationContext, stats: list[tuple[discord.Member, int, int, timedelta]],
                 page_size: int = PAGE_SIZE, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.stats = stats
        self.page_size = page_size
        self.current_page = 0

        self._update_button_states()

    def _page_count(self) -> int:
        return math.ceil(len(self.stats) / self.page_size)

    def _get_page_slice(self, page: int) -> list[tuple[discord.Member, int, int, timedelta]]:
        start = page * self.page_size
        end = start + self.page_size
        return self.stats[start:end]

    def build_embed(self, page: int) -> discord.Embed:
        page_entries = self._get_page_slice(page)

        if not page_entries:
            return discord.Embed(
                title="Galatron Stats", description="**No data**\nThere are no entries.", colour=discord.Colour.red())

        names = []
        longest_name = len("Name")
        for (member, total_uses, total_got, total_duration) in page_entries:
            name = member.name if member is not None else "Unknown"
            names.append(name)
            if len(name) > longest_name:
                longest_name = len(name)

        lines = [f"{'Name'.ljust(longest_name)} | Trys | Success | Duration"]

        for i, (member, total_uses, total_got, total_duration) in enumerate(page_entries):
            lines.append(
                f"{names[i].ljust(longest_name)} | {str(total_uses).rjust(4)} | {str(total_got).rjust(7)} | {td2text(total_duration)}"
            )

        embed = discord.Embed(
            title="Galatron Stats",
            description=f"```{'\n'.join(lines)}```",
        )
        embed.set_footer(text=f"Page {page + 1}/{self._page_count()}")
        return embed

    def _update_button_states(self) -> None:
        page_count = self._page_count()

        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= page_count - 1

    async def _edit(self, interaction: discord.Interaction):
        self._update_button_states()
        embed = self.build_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="⬅️")
    async def prev_button(self, _: discord.ui.Button, interaction: discord.Interaction):
        # optional: nur Command-Author darf klicken
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()

        if self.current_page > 0:
            self.current_page -= 1

        return await self._edit(interaction)

    @button(label="➡️")
    async def next_button(self, _: discord.ui.Button, interaction: discord.Interaction):
        # optional: nur Command-Author darf klicken
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()

        if self.current_page < self._page_count() - 1:
            self.current_page += 1

        return await self._edit(interaction)
