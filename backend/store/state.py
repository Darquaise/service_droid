from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HostRoleData:
    role_id: int
    cooldown: int
    unit: str


@dataclass(slots=True)
class LfgChannelData:
    channel_id: int
    role_ids: list[int]


@dataclass(slots=True)
class AttemptData:
    member_id: int
    occurred_at: float  # epoch seconds
    won: bool


@dataclass(slots=True)
class PeriodData:
    """one entry of a setting timeline: the value in force from ``valid_from`` on"""

    valid_from: float  # epoch seconds
    value: float


@dataclass(slots=True)
class TriviaChannelData:
    channel_id: int
    list_name: str
    schedule: str
    response: int
    mode: str
    order: str
    next_index: int


@dataclass(slots=True)
class MinecraftChannelData:
    channel_id: int
    address: str


@dataclass(slots=True)
class QuestionData:
    local_id: int
    title: str
    question: list[str]
    answer: str
    answer_context: str


@dataclass(slots=True)
class GuildState:
    guild_id: int
    name: str
    host_roles: list[HostRoleData] = field(default_factory=list)
    lfg_channels: list[LfgChannelData] = field(default_factory=list)
    galatron_role_id: int | None = None
    galatron_channels: list[int] = field(default_factory=list)
    galatron_attempts: list[AttemptData] = field(default_factory=list)
    galatron_cooldowns: list[PeriodData] = field(default_factory=list)
    galatron_chances: list[PeriodData] = field(default_factory=list)
    trivia_channels: list[TriviaChannelData] = field(default_factory=list)
    minecraft_channels: list[MinecraftChannelData] = field(default_factory=list)


@dataclass(slots=True)
class LoadedState:
    guilds: dict[int, GuildState] = field(default_factory=dict)
    trivia: dict[int, dict[str, list[QuestionData]]] = field(default_factory=dict)
