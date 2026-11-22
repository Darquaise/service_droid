import math
import discord
from discord.ui import ActionRow, Button, Container, DesignerView, Separator, TextDisplay

from .context import ApplicationContext, Interaction


class PagedCardView(DesignerView):
    """A components v2 view: one card (title, body, page footer, ⬅️ ➡️) over a list of entries.

    Subclasses implement ``build_body``; only the user who ran the command can page.
    """

    accent_color: int | None = None

    def __init__(
        self,
        ctx: ApplicationContext,
        entries: list,
        title: str,
        page_size: int,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self.ctx = ctx
        self.entries = entries
        self.title = title
        self.page_size = page_size
        self.current_page = 1

        self.prev_button = Button(label="⬅️")
        self.prev_button.callback = self._on_prev
        self.next_button = Button(label="➡️")
        self.next_button.callback = self._on_next
        self.render()

    def total_pages(self) -> int:
        return max(1, math.ceil(len(self.entries) / self.page_size))

    def page_entries(self, page: int) -> list:
        start = (page - 1) * self.page_size
        return self.entries[start : start + self.page_size]

    def build_body(self, page: int) -> list:
        raise NotImplementedError

    def render(self) -> None:
        self.clear_items()
        total = self.total_pages()
        items: list = [TextDisplay(f"## {self.title}"), *self.build_body(self.current_page)]
        if total > 1:
            items.append(TextDisplay(f"-# Page {self.current_page}/{total}"))
        self.prev_button.disabled = self.current_page <= 1
        self.next_button.disabled = self.current_page >= total
        items += [Separator(), ActionRow(self.prev_button, self.next_button)]
        self.add_item(Container(*items, colour=self.accent_color))

    async def _edit(self, interaction: Interaction):
        self.render()
        await interaction.response.edit_message(view=self, allowed_mentions=discord.AllowedMentions.none())

    async def _on_prev(self, interaction: Interaction):
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()

        if self.current_page > 1:
            self.current_page -= 1

        return await self._edit(interaction)

    async def _on_next(self, interaction: Interaction):
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()

        if self.current_page < self.total_pages():
            self.current_page += 1

        return await self._edit(interaction)
