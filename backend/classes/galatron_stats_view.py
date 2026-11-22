from datetime import timedelta

import discord
from discord.ui import Separator, TextDisplay

from converters import td2text
from .paged_card_view import PagedCardView

PAGE_SIZE = 15
NO_DATA_COLOR = 0xED4245

StatsEntry = tuple[discord.Member, int, int, timedelta]


class GalatronStatsView(PagedCardView):
    def __init__(self, ctx, stats: list[StatsEntry], page_size: int = PAGE_SIZE, timeout: float = 120):
        super().__init__(ctx, stats, "Galatron Stats", page_size, timeout)

    @property
    def accent_color(self) -> int | None:
        return super().accent_color if self.entries else NO_DATA_COLOR

    def build_body(self, page: int) -> list:
        if not self.entries:
            return [Separator(), TextDisplay("**No data**\nThere are no entries.")]

        first_rank = (page - 1) * self.page_size + 1
        lines = []
        for offset, (member, tries, won, duration) in enumerate(self.page_entries(page)):
            line = f"`{first_rank + offset:>2}.` {member.mention} · {tries} tries"
            if won:
                line += f" · {won} won · {td2text(duration)}"
            lines.append(line)
        return [Separator(), TextDisplay("\n".join(lines))]
