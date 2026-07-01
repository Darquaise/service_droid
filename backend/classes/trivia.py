from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
import discord
from croniter import croniter

from store import trivia_repo

from .trivia_modes import MODE_TIMED, ORDER_RANDOM

if TYPE_CHECKING:
    from store.state import QuestionData


class TriviaQuestion:
    __slots__ = "id", "title", "question", "answer", "answer_context"

    def __init__(self, trivia_id: int, title: str, question: list[str], answer: str, answer_context: str):
        self.id = trivia_id
        self.title = title
        self.question = question
        self.answer = answer
        self.answer_context = answer_context


class TriviaChannelConfig:
    __slots__ = (
        "channel_id", "list_name", "schedule", "response", "mode", "order",
        "_next_index", "pending",
    )

    def __init__(
            self, channel_id: int, list_name: str, schedule: str, response: int,
            mode: str = MODE_TIMED, order: str = ORDER_RANDOM, next_index: int = 0,
    ):
        self.channel_id = channel_id
        self.list_name = list_name
        self.schedule = schedule
        self.response = response
        self.mode = mode
        self.order = order

        self._next_index = next_index
        self.pending: dict | None = None

    def set_pending(self, due_at: float, question: "TriviaQuestion", wording: str) -> None:
        self.pending = {
            "due_at": due_at,
            "title": question.title,
            "question": wording,
            "answer": question.answer,
            "answer_context": question.answer_context,
        }

    def clear_pending(self) -> None:
        self.pending = None

    def next_index(self, length: int) -> int:
        idx = self._next_index % length
        self._next_index = idx + 1
        return idx

    @property
    def next_index_value(self) -> int:
        return self._next_index

    def next_fire(self, now: datetime | None = None) -> datetime:
        base = now if now is not None else datetime.now(timezone.utc)
        return croniter(self.schedule, base).get_next(datetime)

    def next_fire_discord(self) -> str:
        ts = int(self.next_fire().timestamp())
        return f"<t:{ts}:F> (<t:{ts}:R>)"

    @staticmethod
    def is_valid_cron(expr: str) -> bool:
        return croniter.is_valid(expr)


class TriviaHandler:
    _instances: dict[int, "TriviaHandler"] = {}

    __slots__ = ("guild", "lists")

    def __init__(self, guild: discord.Guild, lists: dict[str, list[TriviaQuestion]]):
        self.guild = guild
        self.lists = lists
        TriviaHandler._instances[guild.id] = self

    @property
    def guild_id(self) -> int:
        return self.guild.id

    @classmethod
    def get(cls, guild_id: int) -> "TriviaHandler | None":
        return cls._instances.get(guild_id)

    @classmethod
    def get_or_create(cls, guild: discord.Guild) -> "TriviaHandler":
        existing = cls._instances.get(guild.id)
        if existing is not None:
            return existing
        return cls(guild, {})

    @classmethod
    def load_from_state(
            cls, bot: discord.Client, trivia_state: dict[int, dict[str, list["QuestionData"]]]
    ) -> None:
        for guild_id, lists_data in trivia_state.items():
            guild = bot.get_guild(guild_id)
            if guild is not None:
                cls.replace_for_guild(guild, lists_data)

    @classmethod
    def replace_for_guild(
            cls, guild: discord.Guild, lists_data: dict[str, list["QuestionData"]]
    ) -> "TriviaHandler":
        lists: dict[str, list[TriviaQuestion]] = {
            name: [
                TriviaQuestion(q.local_id, q.title, q.question, q.answer, q.answer_context) for q in questions
            ]
            for name, questions in lists_data.items()
        }
        return cls(guild, lists)

    def get_list_names(self) -> list[str]:
        return list(self.lists.keys())

    def has_list(self, name: str) -> bool:
        return name in self.lists

    async def add_list(self, name: str) -> bool:
        if name in self.lists:
            return False
        self.lists[name] = []
        await trivia_repo.add_list(self.guild_id, name)
        return True

    async def remove_list(self, name: str) -> bool:
        if name not in self.lists:
            return False
        del self.lists[name]
        await trivia_repo.remove_list(self.guild_id, name)
        return True

    async def add_question(
            self, list_name: str, title: str, question: list[str], answer: str, answer_context: str
    ) -> TriviaQuestion | None:
        if list_name not in self.lists:
            return None
        questions = self.lists[list_name]
        next_id = max((q.id for q in questions), default=0) + 1
        new_q = TriviaQuestion(next_id, title, question, answer, answer_context)
        questions.append(new_q)
        await trivia_repo.add_question(self.guild_id, list_name, next_id, title, question, answer, answer_context)
        return new_q

    async def remove_question(self, list_name: str, trivia_id: int) -> bool:
        if list_name not in self.lists:
            return False
        questions = self.lists[list_name]
        for i, q in enumerate(questions):
            if q.id == trivia_id:
                del questions[i]
                await trivia_repo.remove_question(self.guild_id, list_name, trivia_id)
                return True
        return False

    def find_question(self, list_name: str, trivia_id: int) -> TriviaQuestion | None:
        if list_name not in self.lists:
            return None
        for q in self.lists[list_name]:
            if q.id == trivia_id:
                return q
        return None

    async def add_variation(self, list_name: str, trivia_id: int, wording: str) -> TriviaQuestion | None:
        q = self.find_question(list_name, trivia_id)
        if q is None:
            return None
        q.question.append(wording)
        await trivia_repo.set_question_wordings(self.guild_id, list_name, trivia_id, q.question)
        return q
