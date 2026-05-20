import asyncio
import math
from datetime import timedelta

import discord
from discord.ui import View, button

from converters.time import td2text_long
from .context import ApplicationContext, Interaction

PAGE_SIZE = 10
PODIUM_COLORS = [0xFFD700, 0xC0C0C0, 0xCD7F32]
PODIUM_MEDALS = ["🥇", "🥈", "🥉"]
BG_COLOR = 0x2B2D31
PRIME_DELAY = .5
SPACER_URL = "https://cdn.discordapp.com/attachments/790786316408324127/1506467803912208434/spacer_800x1.png"

LeaderboardEntry = tuple[discord.Member, timedelta, int]


class GalatronLeaderboardView(View):
    def __init__(
            self,
            ctx: ApplicationContext,
            leaderboard: list[LeaderboardEntry],
            title: str,
            timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.leaderboard = leaderboard
        self.title = title
        self.current_page = 1
        self.primed_pages: set[int] = set()
        self.message: discord.Message | None = None
        self._update_button_states()

    def total_pages(self) -> int:
        if len(self.leaderboard) <= PAGE_SIZE:
            return 1
        return math.ceil(len(self.leaderboard) / PAGE_SIZE)

    def _rest_entries(self, page: int) -> list[LeaderboardEntry]:
        if page == 1:
            return self.leaderboard[3:PAGE_SIZE]
        start = (page - 1) * PAGE_SIZE
        return self.leaderboard[start:start + PAGE_SIZE]

    def _page_members(self, page: int) -> list[discord.Member]:
        members: list[discord.Member] = []
        if page == 1:
            members.extend(m for m, _, _ in self.leaderboard[:3])
        members.extend(m for m, _, _ in self._rest_entries(page))
        return members

    def build_embeds(self, page: int) -> list[discord.Embed]:
        embeds: list[discord.Embed] = []
        total = self.total_pages()

        if page == 1:
            for i, (member, duration, amount) in enumerate(self.leaderboard[:3]):
                line = (
                    f"{PODIUM_MEDALS[i]} **{i + 1}.** {member.mention} "
                    f"({amount}x) – {td2text_long(duration)}"
                )
                embed = discord.Embed(
                    description=line,
                    color=PODIUM_COLORS[i],
                )
                if i == 0:
                    embed.title = self.title
                embeds.append(embed)

        rest = self._rest_entries(page)
        if rest:
            start_rank = 4 if page == 1 else (page - 1) * PAGE_SIZE + 1
            lines = [
                f"**{start_rank + offset}.** {member.mention} "
                f"({amount}x) – {td2text_long(duration)}"
                for offset, (member, duration, amount) in enumerate(rest)
            ]
            rest_embed = discord.Embed(
                description="\n".join(lines),
                color=BG_COLOR,
            )
            if page != 1:
                rest_embed.title = self.title
            embeds.append(rest_embed)

        for embed in embeds:
            embed.set_image(url=SPACER_URL)

        if total > 1 and embeds:
            embeds[-1].set_footer(text=f"Page {page}/{total}")

        return embeds

    def build_content(self, page: int) -> str | None:
        if page in self.primed_pages:
            return None
        members = self._page_members(page)
        if not members:
            return None
        return " ".join(m.mention for m in members)

    def _update_button_states(self) -> None:
        total = self.total_pages()
        self.prev_button.disabled = self.current_page <= 1
        self.next_button.disabled = self.current_page >= total

    async def _edit(self, interaction: Interaction):
        self._update_button_states()
        page = self.current_page
        content = self.build_content(page)
        embeds = self.build_embeds(page)
        self.primed_pages.add(page)

        await interaction.response.edit_message(
            content=content or "",
            embeds=embeds,
            view=self,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        if content and self.message is not None:
            await asyncio.sleep(PRIME_DELAY)
            try:
                await self.message.edit(
                    content="",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                pass

    @button(label="⬅️")
    async def prev_button(self, _: discord.ui.Button, interaction: Interaction):
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()

        if self.current_page > 1:
            self.current_page -= 1

        return await self._edit(interaction)

    @button(label="➡️")
    async def next_button(self, _: discord.ui.Button, interaction: Interaction):
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()

        if self.current_page < self.total_pages():
            self.current_page += 1

        return await self._edit(interaction)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
