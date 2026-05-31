from __future__ import annotations

import os
from datetime import datetime, timezone

import discord
from croniter import croniter

from ios import read_json, write_json
from .trivia_modes import MODE_TIMED, ORDER_RANDOM


class TriviaQuestion:
    __slots__ = "id", "title", "question", "answer", "answer_context"

    def __init__(self, trivia_id: int, title: str, question: list[str], answer: str, answer_context: str):
        self.id = trivia_id
        self.title = title
        self.question = question
        self.answer = answer
        self.answer_context = answer_context

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "question": self.question,
            "answer": self.answer,
            "answer_context": self.answer_context,
        }

    @classmethod
    def from_json(cls, data: dict) -> "TriviaQuestion":
        question = data["question"]
        if isinstance(question, str):
            question = [question]
        return cls(
            trivia_id=int(data["id"]),
            title=data["title"],
            question=question,
            answer=data["answer"],
            answer_context=data.get("answer_context", ""),
        )


class TriviaChannelConfig:
    __slots__ = (
        "channel_id", "list_name", "schedule", "response", "mode", "order",
        "_next_index", "pending",
    )

    def __init__(
            self, channel_id: int, list_name: str, schedule: str, response: int,
            mode: str = MODE_TIMED, order: str = ORDER_RANDOM,
    ):
        self.channel_id = channel_id
        self.list_name = list_name
        self.schedule = schedule
        self.response = response
        self.mode = mode
        self.order = order

        self._next_index = 0
        self.pending: dict | None = None

    def to_json(self) -> dict:
        data = {
            "list": self.list_name,
            "schedule": self.schedule,
            "response": self.response,
            "mode": self.mode,
            "order": self.order,
        }
        if self._next_index:
            data["next_index"] = self._next_index
        return data

    @classmethod
    def from_json(cls, channel_id: int, data: dict) -> "TriviaChannelConfig":
        obj = cls(
            channel_id=channel_id,
            list_name=data["list"],
            schedule=data["schedule"],
            response=int(data["response"]),
            mode=data.get("mode", MODE_TIMED),
            order=data.get("order", ORDER_RANDOM),
        )
        obj._next_index = int(data.get("next_index", 0))
        return obj

    def set_pending(self, due_at: float, question: "TriviaQuestion") -> None:
        self.pending = {
            "due_at": due_at,
            "title": question.title,
            "answer": question.answer,
            "answer_context": question.answer_context,
        }

    def clear_pending(self) -> None:
        self.pending = None

    def next_index(self, length: int) -> int:
        idx = self._next_index % length
        self._next_index = idx + 1
        return idx

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
    def load_all(cls, folder_path: str, bot: discord.Client) -> None:
        if not os.path.isdir(folder_path):
            return
        for filename in os.listdir(folder_path):
            if not filename.endswith(".json"):
                continue
            stem = filename[:-len(".json")]
            if not stem.isdigit():
                continue
            guild_id = int(stem)
            guild = bot.get_guild(guild_id)
            if guild is None:
                continue
            data = read_json(os.path.join(folder_path, filename))
            lists: dict[str, list[TriviaQuestion]] = {
                name: [TriviaQuestion.from_json(q) for q in questions]
                for name, questions in data.items()
            }
            cls(guild, lists)

    def get_list_names(self) -> list[str]:
        return list(self.lists.keys())

    def has_list(self, name: str) -> bool:
        return name in self.lists

    def add_list(self, name: str) -> bool:
        if name in self.lists:
            return False
        self.lists[name] = []
        return True

    def remove_list(self, name: str) -> bool:
        if name not in self.lists:
            return False
        del self.lists[name]
        return True

    def add_question(
            self, list_name: str, title: str, question: list[str], answer: str, answer_context: str
    ) -> TriviaQuestion | None:
        if list_name not in self.lists:
            return None
        questions = self.lists[list_name]
        next_id = max((q.id for q in questions), default=0) + 1
        new_q = TriviaQuestion(next_id, title, question, answer, answer_context)
        questions.append(new_q)
        return new_q

    def remove_question(self, list_name: str, trivia_id: int) -> bool:
        if list_name not in self.lists:
            return False
        questions = self.lists[list_name]
        for i, q in enumerate(questions):
            if q.id == trivia_id:
                del questions[i]
                return True
        return False

    def to_json(self) -> dict:
        return {name: [q.to_json() for q in questions] for name, questions in self.lists.items()}

    def save(self, folder_path: str) -> None:
        os.makedirs(folder_path, exist_ok=True)
        path = os.path.join(folder_path, f"{self.guild_id}.json")
        write_json(path, self.to_json())
