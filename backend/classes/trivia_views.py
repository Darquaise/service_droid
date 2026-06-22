import textwrap

import discord
from discord.ui import View, button

from .context import ApplicationContext, Interaction
from .trivia import TriviaQuestion

# Discord wraps code blocks inside embeds at 40 columns on desktop.
LINE_WIDTH = 40
# Embed description hard limit is 4096 — keep margin for ``` fences and newlines.
MAX_BODY = 4000
SEPARATOR = "-" * LINE_WIDTH
TITLE_RULE = "=" * LINE_WIDTH


def _wrap(text: str) -> list[str]:
    if not text:
        return [""]
    wrapped = textwrap.wrap(
        text,
        width=LINE_WIDTH,
        break_long_words=True,
        break_on_hyphens=False,
        replace_whitespace=False,
        drop_whitespace=True,
    )
    return wrapped or [""]


def _format_question(q: TriviaQuestion) -> str:
    lines: list[str] = []

    lines.extend(_wrap(f"#{q.id}  {q.title or '(untitled)'}"))
    lines.append(TITLE_RULE)

    if q.question:
        multi = len(q.question) > 1
        for i, part in enumerate(q.question):
            if i > 0:
                lines.append("")
            prefix = f"[{i + 1}] " if multi else ""
            lines.extend(_wrap(f"{prefix}{part}"))
    else:
        lines.append("")

    lines.append("")
    lines.extend(_wrap(f"A: {q.answer}"))

    if q.answer_context:
        lines.append("")
        lines.extend(_wrap(q.answer_context))

    return "\n".join(lines)


class TriviaQuestionPaginatorView(View):
    def __init__(
            self, ctx: ApplicationContext, list_name: str, questions: list[TriviaQuestion],
            timeout: float = 120,
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.list_name = list_name
        self.questions = questions
        self.current_page = 0
        self.pages: list[tuple[int, int]] = self._compute_pages()
        self._update_button_states()

    def _compute_pages(self) -> list[tuple[int, int]]:
        if not self.questions:
            return []
        pages: list[tuple[int, int]] = []
        sep_len = len(SEPARATOR) + 2  # newline before + after
        start = 0
        n = len(self.questions)
        while start < n:
            end = start
            size = 0
            while end < n:
                block_len = len(_format_question(self.questions[end]))
                extra = block_len + (sep_len if end > start else 0)
                if end > start and size + extra > MAX_BODY:
                    break
                size += extra
                end += 1
            if end == start:
                end = start + 1  # single oversized block — show alone
            pages.append((start, end))
            start = end
        return pages

    def _page_count(self) -> int:
        return max(1, len(self.pages))

    def build_embed(self, page: int) -> discord.Embed:
        if not self.questions:
            return discord.Embed(
                title=f"Trivia list: {self.list_name}",
                description="**Empty**\nThis list has no questions yet.",
                colour=0xffd700,
            )

        start, end = self.pages[page]
        sections = [_format_question(q) for q in self.questions[start:end]]
        body = f"\n{SEPARATOR}\n".join(sections)

        embed = discord.Embed(
            title=f"Trivia list: {self.list_name}",
            description=f"```\n{body}\n```",
            colour=0xffd700,
        )
        embed.set_footer(
            text=f"Page {page + 1}/{self._page_count()} • {len(self.questions)} questions"
        )
        return embed

    def _update_button_states(self) -> None:
        page_count = self._page_count()
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= page_count - 1

    async def _edit(self, interaction: Interaction):
        self._update_button_states()
        embed = self.build_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="⬅️")
    async def prev_button(self, _: discord.ui.Button, interaction: Interaction):
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
        return await self._edit(interaction)

    @button(label="➡️")
    async def next_button(self, _: discord.ui.Button, interaction: Interaction):
        if interaction.user.id != self.ctx.user.id:
            return await interaction.response.defer()
        if self.current_page < self._page_count() - 1:
            self.current_page += 1
        return await self._edit(interaction)
