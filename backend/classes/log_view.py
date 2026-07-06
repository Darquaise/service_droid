import os
import re

import discord
from discord.ui import View, button, select

from .context import ApplicationContext, Interaction

LINES_PER_PAGE_OPTIONS = [10, 20, 30, 50, 100]
DEFAULT_LINES_PER_PAGE = 30
MAX_BUFFER_LINES = 10000
MAX_LINE_CHARS = 250
MAX_DESCRIPTION_CHARS = 4000

_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _read_tail(path: str, max_lines: int) -> list[str]:
    if not os.path.exists(path):
        return []

    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        block = 8192
        data = b""
        pos = size
        while pos > 0 and data.count(b"\n") <= max_lines:
            read_size = min(block, pos)
            pos -= read_size
            f.seek(pos)
            data = f.read(read_size) + data

    text = data.decode("utf-8", errors="replace")
    text = _ANSI_RE.sub("", text)
    lines = text.splitlines()
    # If we stopped before reaching the start of the file, the first line was
    # cut mid-line by the block boundary — drop it.
    if pos > 0:
        lines = lines[1:]
    return lines[-max_lines:]


class LogView(View):
    def __init__(
            self,
            ctx: ApplicationContext,
            log_path: str,
            lines_per_page: int = DEFAULT_LINES_PER_PAGE,
            timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.log_path = log_path
        self.lines_per_page = lines_per_page
        self.lines: list[str] = []
        self.start_line = 0

        self._load()
        self._anchor_end()
        self._update_states()

    def _load(self) -> None:
        self.lines = _read_tail(self.log_path, MAX_BUFFER_LINES)

    def _max_start(self) -> int:
        return max(0, len(self.lines) - self.lines_per_page)

    def _anchor_end(self) -> None:
        self.start_line = self._max_start()

    def _clamp(self) -> None:
        if self.start_line < 0:
            self.start_line = 0
        elif self.start_line > self._max_start():
            self.start_line = self._max_start()

    def build_embed(self) -> discord.Embed:
        if not self.lines:
            return discord.Embed(
                title="Bot Log",
                description=f"Log file is empty or not found:\n`{self.log_path}`",
                colour=discord.Colour.red(),
            )

        end = self.start_line + self.lines_per_page
        page = self.lines[self.start_line:end]

        rendered = []
        for line in page:
            if len(line) > MAX_LINE_CHARS:
                line = line[: MAX_LINE_CHARS - 1] + "…"
            rendered.append(line.replace("```", "''`"))

        body = "\n".join(rendered)
        if len(body) > MAX_DESCRIPTION_CHARS:
            body = body[: MAX_DESCRIPTION_CHARS - 1] + "…"

        total = len(self.lines)
        embed = discord.Embed(
            title="Bot Log",
            description=f"```\n{body}\n```",
        )
        embed.set_footer(
            text=(
                f"Lines {self.start_line + 1}-{min(end, total)} / {total}"
                f" • {self.lines_per_page} per page"
            )
        )
        return embed

    def _update_states(self) -> None:
        max_start = self._max_start()
        at_start = self.start_line <= 0
        at_end = self.start_line >= max_start

        self.first_btn.disabled = at_start
        self.prev_page_btn.disabled = at_start
        self.prev_line_btn.disabled = at_start
        self.next_line_btn.disabled = at_end
        self.next_page_btn.disabled = at_end
        self.last_btn.disabled = at_end

        for option in self.lines_select.options:
            option.default = int(option.value) == self.lines_per_page

    def _check_user(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.ctx.user.id

    async def _edit(self, interaction: Interaction) -> None:
        self._clamp()
        self._update_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @button(label="⏮", row=0)
    async def first_btn(self, _: discord.ui.Button, interaction: Interaction):
        if not self._check_user(interaction):
            return await interaction.response.defer()
        self.start_line = 0
        return await self._edit(interaction)

    @button(label="⏪", row=0)
    async def prev_page_btn(self, _: discord.ui.Button, interaction: Interaction):
        if not self._check_user(interaction):
            return await interaction.response.defer()
        self.start_line -= self.lines_per_page
        return await self._edit(interaction)

    @button(label="🔄", row=0)
    async def refresh_btn(self, _: discord.ui.Button, interaction: Interaction):
        if not self._check_user(interaction):
            return await interaction.response.defer()
        was_at_end = self.start_line >= self._max_start()
        self._load()
        if was_at_end:
            self._anchor_end()
        return await self._edit(interaction)

    @button(label="⏩", row=0)
    async def next_page_btn(self, _: discord.ui.Button, interaction: Interaction):
        if not self._check_user(interaction):
            return await interaction.response.defer()
        self.start_line += self.lines_per_page
        return await self._edit(interaction)

    @button(label="⏭", row=0)
    async def last_btn(self, _: discord.ui.Button, interaction: Interaction):
        if not self._check_user(interaction):
            return await interaction.response.defer()
        self._anchor_end()
        return await self._edit(interaction)

    @button(label="⬆ Line", row=1)
    async def prev_line_btn(self, _: discord.ui.Button, interaction: Interaction):
        if not self._check_user(interaction):
            return await interaction.response.defer()
        self.start_line -= 1
        return await self._edit(interaction)

    @button(label="⬇ Line", row=1)
    async def next_line_btn(self, _: discord.ui.Button, interaction: Interaction):
        if not self._check_user(interaction):
            return await interaction.response.defer()
        self.start_line += 1
        return await self._edit(interaction)

    @select(
        placeholder="Lines per page",
        row=2,
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label=f"{n} lines", value=str(n))
            for n in LINES_PER_PAGE_OPTIONS
        ],
    )
    async def lines_select(self, sel: discord.ui.Select, interaction: Interaction):
        values = sel.values
        if not self._check_user(interaction) or not values:
            return await interaction.response.defer()
        new_lpp = int(values[0])
        was_at_end = self.start_line >= self._max_start()
        self.lines_per_page = new_lpp
        if was_at_end:
            self._anchor_end()
        return await self._edit(interaction)
