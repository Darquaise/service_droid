from datetime import timedelta

import discord
from discord.ui import Separator, TextDisplay

from converters.time import td2text_long
from .paged_card_view import PagedCardView

PAGE_SIZE = 15
PODIUM_MEDALS = ["🥇", "🥈", "🥉"]

LeaderboardEntry = tuple[discord.Member, timedelta, int]


class GalatronLeaderboardView(PagedCardView):
    def __init__(self, ctx, leaderboard: list[LeaderboardEntry], title: str, timeout: float = 300):
        super().__init__(ctx, leaderboard, title, PAGE_SIZE, timeout)

    @property
    def leaderboard(self) -> list[LeaderboardEntry]:
        return self.entries

    @staticmethod
    def _stats(duration: timedelta, amount: int) -> str:
        return f"{amount}x · {td2text_long(duration)}"

    def build_body(self, page: int) -> list:
        entries = self.page_entries(page)
        items: list = []

        podium = entries[:3] if page == 1 else []
        if podium:
            items.append(Separator())
            items.append(
                TextDisplay(
                    "\n".join(
                        f"### {PODIUM_MEDALS[i]} {member.mention}\n-# {self._stats(duration, amount)}"
                        for i, (member, duration, amount) in enumerate(podium)
                    )
                )
            )

        rest = entries[len(podium) :]
        if rest:
            first_rank = (page - 1) * PAGE_SIZE + len(podium) + 1
            items.append(Separator())
            items.append(
                TextDisplay(
                    "\n".join(
                        f"`{first_rank + offset:>2}.` {member.mention} · {self._stats(duration, amount)}"
                        for offset, (member, duration, amount) in enumerate(rest)
                    )
                )
            )
        return items
