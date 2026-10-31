from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .engine import session_factory
from .notify import emit_change
from .models import (
    GalatronAttemptRow,
    GalatronChanceRow,
    GalatronChannelRow,
    GuildRow,
    MinecraftStatusChannelRow,
    LfgChannelRoleRow,
    LfgChannelRow,
    LfgHostRoleRow,
    TriviaChannelRow,
    TriviaListRow,
    TriviaPendingRow,
    TriviaQuestionRow,
)
from .state import (
    AttemptData,
    GuildState,
    HostRoleData,
    LfgChannelData,
    LoadedState,
    MinecraftChannelData,
    PeriodData,
    QuestionData,
    TriviaChannelData,
)

if TYPE_CHECKING:
    from classes.trivia import TriviaChannelConfig, TriviaQuestion

# Sentinel: "leave this column untouched on conflict" (distinct from an explicit None).
_UNSET: Any = object()


def _to_dt(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def _to_epoch(dt: datetime) -> float:
    return dt.timestamp()


class _Repo:
    @staticmethod
    def _session() -> AsyncSession:
        return session_factory()()


class GuildRepo(_Repo):
    async def ensure_guilds(self, guilds: Iterable[tuple[int, str]]) -> None:
        """Insert a row for every guild the bot is in (refresh the name); never
        overwrites existing Galatron/Trivia settings. Guarantees the FK parent
        exists before any per-aggregate write. (No notify: startup bookkeeping.)"""
        async with self._session() as s, s.begin():
            for guild_id, name in guilds:
                await s.execute(
                    pg_insert(GuildRow)
                    .values(guild_id=guild_id, name=name)
                    .on_conflict_do_update(index_elements=["guild_id"], set_={"name": name})
                )

    async def set_galatron_role(self, guild_id: int, role_id: int | None) -> None:
        await self._update_guild(guild_id, galatron_role_id=role_id)

    async def set_galatron_register(self, guild_id: int, register: str) -> None:
        await self._update_guild(guild_id, galatron_register=register)

    async def _update_guild(self, guild_id: int, **values: Any) -> None:
        async with self._session() as s, s.begin():
            await s.execute(update(GuildRow).where(GuildRow.guild_id == guild_id).values(**values))
            await emit_change(s, guild_id)


class LfgRepo(_Repo):
    async def upsert_host_role(self, guild_id: int, role_id: int, cooldown: int, unit: str) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(LfgHostRoleRow)
                .values(guild_id=guild_id, role_id=role_id, cooldown=cooldown, cooldown_unit=unit)
                .on_conflict_do_update(
                    index_elements=["guild_id", "role_id"],
                    set_={"cooldown": cooldown, "cooldown_unit": unit},
                )
            )
            await emit_change(s, guild_id)

    async def delete_host_role(self, guild_id: int, role_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(LfgHostRoleRow).where(
                    LfgHostRoleRow.guild_id == guild_id, LfgHostRoleRow.role_id == role_id
                )
            )
            await emit_change(s, guild_id)

    async def set_channel_roles(self, guild_id: int, channel_id: int, role_ids: list[int]) -> None:
        """Upsert the channel and replace its full set of mentioned roles."""
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(LfgChannelRow)
                .values(guild_id=guild_id, channel_id=channel_id)
                .on_conflict_do_nothing(index_elements=["guild_id", "channel_id"])
            )
            await s.execute(
                delete(LfgChannelRoleRow).where(
                    LfgChannelRoleRow.guild_id == guild_id,
                    LfgChannelRoleRow.channel_id == channel_id,
                )
            )
            if role_ids:
                await s.execute(
                    insert(LfgChannelRoleRow),
                    [
                        {"guild_id": guild_id, "channel_id": channel_id, "role_id": rid}
                        for rid in role_ids
                    ],
                )
            await emit_change(s, guild_id)

    async def delete_channel(self, guild_id: int, channel_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(LfgChannelRow).where(
                    LfgChannelRow.guild_id == guild_id, LfgChannelRow.channel_id == channel_id
                )
            )  # roles cascade via FK
            await emit_change(s, guild_id)


class GalatronRepo(_Repo):
    async def add_channel(self, guild_id: int, channel_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(GalatronChannelRow)
                .values(guild_id=guild_id, channel_id=channel_id)
                .on_conflict_do_nothing(index_elements=["guild_id", "channel_id"])
            )
            await emit_change(s, guild_id)

    async def delete_channel(self, guild_id: int, channel_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(GalatronChannelRow).where(
                    GalatronChannelRow.guild_id == guild_id,
                    GalatronChannelRow.channel_id == channel_id,
                )
            )
            await emit_change(s, guild_id)

    async def add_attempt(
        self, guild_id: int, member_id: int, occurred_at: float, won: bool
    ) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                insert(GalatronAttemptRow).values(
                    guild_id=guild_id,
                    member_id=member_id,
                    occurred_at=_to_dt(occurred_at),
                    won=won,
                )
            )
            await emit_change(s, guild_id)

    async def add_chance(self, guild_id: int, chance: float, valid_from: float) -> None:
        await self._add_period(GalatronChanceRow, guild_id, valid_from, chance=chance)

    async def move_chance_start(self, guild_id: int, old: float, new: float) -> None:
        await self._move_period(GalatronChanceRow, guild_id, old, new)

    async def _add_period(self, row, guild_id: int, valid_from: float, **value: Any) -> None:
        """Start a new period of a setting timeline (a second change within the same
        instant overwrites the first — the value in force is what counts)."""
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(row)
                .values(guild_id=guild_id, valid_from=_to_dt(valid_from), **value)
                .on_conflict_do_update(index_elements=["guild_id", "valid_from"], set_=value)
            )
            await emit_change(s, guild_id)

    async def _move_period(self, row, guild_id: int, old: float, new: float) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                update(row)
                .where(row.guild_id == guild_id, row.valid_from == _to_dt(old))
                .values(valid_from=_to_dt(new))
            )
            await emit_change(s, guild_id)

    async def clear_attempts(self, guild_id: int) -> None:
        """Wipe every attempt (channels/role/chance kept)."""
        async with self._session() as s, s.begin():
            await s.execute(
                delete(GalatronAttemptRow).where(GalatronAttemptRow.guild_id == guild_id)
            )
            await emit_change(s, guild_id)


class MinecraftRepo(_Repo):
    async def upsert_channel(self, guild_id: int, channel_id: int, address: str) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(MinecraftStatusChannelRow)
                .values(guild_id=guild_id, channel_id=channel_id, address=address)
                .on_conflict_do_update(
                    index_elements=["guild_id", "channel_id"], set_={"address": address}
                )
            )
            await emit_change(s, guild_id)

    async def delete_channel(self, guild_id: int, channel_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(MinecraftStatusChannelRow).where(
                    MinecraftStatusChannelRow.guild_id == guild_id,
                    MinecraftStatusChannelRow.channel_id == channel_id,
                )
            )
            await emit_change(s, guild_id)


class TriviaRepo(_Repo):
    async def add_list(self, guild_id: int, name: str) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(TriviaListRow)
                .values(guild_id=guild_id, name=name)
                .on_conflict_do_nothing(index_elements=["guild_id", "name"])
            )
            await emit_change(s, guild_id)

    async def remove_list(self, guild_id: int, name: str) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(TriviaListRow).where(
                    TriviaListRow.guild_id == guild_id, TriviaListRow.name == name
                )
            )  # questions cascade via FK
            await emit_change(s, guild_id)

    async def add_question(
        self,
        guild_id: int,
        list_name: str,
        local_id: int,
        title: str,
        question: list[str],
        answer: str,
        answer_context: str,
    ) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                insert(TriviaQuestionRow).values(
                    guild_id=guild_id,
                    list_name=list_name,
                    local_id=local_id,
                    title=title,
                    question=list(question),
                    answer=answer,
                    answer_context=answer_context,
                )
            )
            await emit_change(s, guild_id)

    async def remove_question(self, guild_id: int, list_name: str, local_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(TriviaQuestionRow).where(
                    TriviaQuestionRow.guild_id == guild_id,
                    TriviaQuestionRow.list_name == list_name,
                    TriviaQuestionRow.local_id == local_id,
                )
            )
            await emit_change(s, guild_id)

    async def set_question_wordings(
        self, guild_id: int, list_name: str, local_id: int, wordings: list[str]
    ) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                update(TriviaQuestionRow)
                .where(
                    TriviaQuestionRow.guild_id == guild_id,
                    TriviaQuestionRow.list_name == list_name,
                    TriviaQuestionRow.local_id == local_id,
                )
                .values(question=list(wordings))
            )
            await emit_change(s, guild_id)

    async def replace_guild(
        self, guild_id: int, lists: dict[str, list["TriviaQuestion"]]
    ) -> None:
        """Replace *all* of a guild's trivia lists/questions (inject 'replace')."""
        async with self._session() as s, s.begin():
            await s.execute(delete(TriviaListRow).where(TriviaListRow.guild_id == guild_id))
            await self._insert_lists(s, guild_id, lists)
            await emit_change(s, guild_id)

    async def replace_list(
        self, guild_id: int, list_name: str, questions: list["TriviaQuestion"]
    ) -> None:
        """Replace a single list's questions (inject 'merge')."""
        async with self._session() as s, s.begin():
            await s.execute(
                delete(TriviaListRow).where(
                    TriviaListRow.guild_id == guild_id, TriviaListRow.name == list_name
                )
            )
            await self._insert_lists(s, guild_id, {list_name: questions})
            await emit_change(s, guild_id)

    @staticmethod
    async def _insert_lists(
        s: AsyncSession, guild_id: int, lists: dict[str, list["TriviaQuestion"]]
    ) -> None:
        for name, questions in lists.items():
            await s.execute(
                pg_insert(TriviaListRow)
                .values(guild_id=guild_id, name=name)
                .on_conflict_do_nothing(index_elements=["guild_id", "name"])
            )
            if questions:
                await s.execute(
                    insert(TriviaQuestionRow),
                    [
                        {
                            "guild_id": guild_id,
                            "list_name": name,
                            "local_id": q.id,
                            "title": q.title,
                            "question": list(q.question),
                            "answer": q.answer,
                            "answer_context": q.answer_context,
                        }
                        for q in questions
                    ],
                )

    async def upsert_channel(self, guild_id: int, config: "TriviaChannelConfig") -> None:
        values = {
            "guild_id": guild_id,
            "channel_id": config.channel_id,
            "list_name": config.list_name,
            "schedule": config.schedule,
            "response": config.response,
            "mode": config.mode,
            "question_order": config.order,
            "next_index": config.next_index_value,
        }
        set_ = {k: v for k, v in values.items() if k not in ("guild_id", "channel_id")}
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(TriviaChannelRow)
                .values(**values)
                .on_conflict_do_update(index_elements=["guild_id", "channel_id"], set_=set_)
            )
            await emit_change(s, guild_id)

    async def delete_channel(self, guild_id: int, channel_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(TriviaChannelRow).where(
                    TriviaChannelRow.guild_id == guild_id,
                    TriviaChannelRow.channel_id == channel_id,
                )
            )
            await emit_change(s, guild_id)

    async def set_channel_next_index(
        self, guild_id: int, channel_id: int, next_index: int
    ) -> None:
        # Bot-owned runtime cursor (single writer: the scheduler) — no notify.
        async with self._session() as s, s.begin():
            await s.execute(
                update(TriviaChannelRow)
                .where(
                    TriviaChannelRow.guild_id == guild_id,
                    TriviaChannelRow.channel_id == channel_id,
                )
                .values(next_index=next_index)
            )

    async def upsert_pending(
        self, channel_id: int, due_at: float, title: str, question: str,
        answer: str, answer_context: str,
    ) -> None:
        # Ephemeral runtime state (channel-scoped) — no notify.
        values = {
            "channel_id": channel_id,
            "due_at": _to_dt(due_at),
            "title": title,
            "question": question,
            "answer": answer,
            "answer_context": answer_context,
        }
        set_ = {k: v for k, v in values.items() if k != "channel_id"}
        async with self._session() as s, s.begin():
            await s.execute(
                pg_insert(TriviaPendingRow)
                .values(**values)
                .on_conflict_do_update(index_elements=["channel_id"], set_=set_)
            )

    async def delete_pending(self, channel_id: int) -> None:
        async with self._session() as s, s.begin():
            await s.execute(
                delete(TriviaPendingRow).where(TriviaPendingRow.channel_id == channel_id)
            )

    async def load_pending(self) -> dict[str, dict]:
        """Mirror of the former ``_pending.json`` (keyed by channel id as string)."""
        async with self._session() as s:
            rows = (await s.execute(select(TriviaPendingRow))).scalars().all()
        return {
            str(r.channel_id): {
                "due_at": _to_epoch(r.due_at),
                "title": r.title,
                "question": r.question,
                "answer": r.answer,
                "answer_context": r.answer_context,
            }
            for r in rows
        }


guild_repo = GuildRepo()
lfg_repo = LfgRepo()
galatron_repo = GalatronRepo()
trivia_repo = TriviaRepo()
minecraft_repo = MinecraftRepo()


# ---------------------------------------------------------------------------
# Read paths: rebuild the in-memory domain from the database.
#   load_state()       — everything, once, at startup
#   load_guild_state() — one guild, for a live reload (store.notify)
# Both return typed structs (store.state) the domain builds its objects from.
# ---------------------------------------------------------------------------
def _build_guild_state(
    g: GuildRow,
    host_roles,
    lfg_channels,
    lfg_channel_roles,
    ga_channels,
    ga_attempts,
    ga_chances,
    tr_channels,
    mc_channels,
) -> GuildState:
    roles_by_c: dict[int, list[int]] = defaultdict(list)
    for r in lfg_channel_roles:
        roles_by_c[r.channel_id].append(r.role_id)
    return GuildState(
        guild_id=g.guild_id,
        name=g.name,
        host_roles=[HostRoleData(r.role_id, r.cooldown, r.cooldown_unit) for r in host_roles],
        lfg_channels=[
            LfgChannelData(c.channel_id, roles_by_c.get(c.channel_id, [])) for c in lfg_channels
        ],
        galatron_role_id=g.galatron_role_id,
        galatron_register=g.galatron_register,
        galatron_channels=[c.channel_id for c in ga_channels],
        galatron_attempts=[
            AttemptData(a.member_id, _to_epoch(a.occurred_at), a.won) for a in ga_attempts
        ],
        galatron_chances=[PeriodData(_to_epoch(c.valid_from), c.chance) for c in ga_chances],
        trivia_channels=[
            TriviaChannelData(
                tc.channel_id, tc.list_name, tc.schedule, tc.response,
                tc.mode, tc.question_order, tc.next_index,
            )
            for tc in tr_channels
        ],
        minecraft_channels=[
            MinecraftChannelData(mc.channel_id, mc.address) for mc in mc_channels
        ],
    )


def _build_lists(tr_lists, tr_questions) -> dict[str, list[QuestionData]]:
    lists: dict[str, list[QuestionData]] = {}
    for lst in tr_lists:
        lists.setdefault(lst.name, [])
    for q in tr_questions:
        lists.setdefault(q.list_name, []).append(
            QuestionData(q.local_id, q.title, list(q.question), q.answer, q.answer_context)
        )
    return lists


async def load_state() -> LoadedState:
    async with session_factory()() as s:
        guild_rows = (await s.execute(select(GuildRow))).scalars().all()
        host_roles = (await s.execute(select(LfgHostRoleRow))).scalars().all()
        lfg_channels = (await s.execute(select(LfgChannelRow))).scalars().all()
        lfg_channel_roles = (await s.execute(select(LfgChannelRoleRow))).scalars().all()
        ga_channels = (await s.execute(select(GalatronChannelRow))).scalars().all()
        ga_attempts = (
            await s.execute(
                select(GalatronAttemptRow).order_by(
                    GalatronAttemptRow.guild_id,
                    GalatronAttemptRow.occurred_at,
                    GalatronAttemptRow.id,
                )
            )
        ).scalars().all()
        ga_chances = (await s.execute(select(GalatronChanceRow))).scalars().all()
        tr_channels = (await s.execute(select(TriviaChannelRow))).scalars().all()
        mc_channels = (await s.execute(select(MinecraftStatusChannelRow))).scalars().all()
        tr_lists = (await s.execute(select(TriviaListRow))).scalars().all()
        tr_questions = (
            await s.execute(
                select(TriviaQuestionRow).order_by(
                    TriviaQuestionRow.guild_id,
                    TriviaQuestionRow.list_name,
                    TriviaQuestionRow.local_id,
                )
            )
        ).scalars().all()

    host_by_g: dict[int, list] = defaultdict(list)
    for r in host_roles:
        host_by_g[r.guild_id].append(r)
    lfg_chan_by_g: dict[int, list] = defaultdict(list)
    for c in lfg_channels:
        lfg_chan_by_g[c.guild_id].append(c)
    lfg_roles_by_g: dict[int, list] = defaultdict(list)
    for r in lfg_channel_roles:
        lfg_roles_by_g[r.guild_id].append(r)
    ga_chan_by_g: dict[int, list] = defaultdict(list)
    for c in ga_channels:
        ga_chan_by_g[c.guild_id].append(c)
    ga_att_by_g: dict[int, list] = defaultdict(list)
    for a in ga_attempts:
        ga_att_by_g[a.guild_id].append(a)
    ga_ch_by_g: dict[int, list] = defaultdict(list)
    for c in ga_chances:
        ga_ch_by_g[c.guild_id].append(c)
    tr_chan_by_g: dict[int, list] = defaultdict(list)
    for tc in tr_channels:
        tr_chan_by_g[tc.guild_id].append(tc)
    mc_chan_by_g: dict[int, list] = defaultdict(list)
    for mc in mc_channels:
        mc_chan_by_g[mc.guild_id].append(mc)
    tr_lists_by_g: dict[int, list] = defaultdict(list)
    for lst in tr_lists:
        tr_lists_by_g[lst.guild_id].append(lst)
    tr_q_by_g: dict[int, list] = defaultdict(list)
    for q in tr_questions:
        tr_q_by_g[q.guild_id].append(q)

    guild_states = {
        g.guild_id: _build_guild_state(
            g,
            host_by_g.get(g.guild_id, []),
            lfg_chan_by_g.get(g.guild_id, []),
            lfg_roles_by_g.get(g.guild_id, []),
            ga_chan_by_g.get(g.guild_id, []),
            ga_att_by_g.get(g.guild_id, []),
            ga_ch_by_g.get(g.guild_id, []),
            tr_chan_by_g.get(g.guild_id, []),
            mc_chan_by_g.get(g.guild_id, []),
        )
        for g in guild_rows
    }
    trivia = {
        gid: _build_lists(tr_lists_by_g.get(gid, []), tr_q_by_g.get(gid, []))
        for gid in {lst.guild_id for lst in tr_lists} | {q.guild_id for q in tr_questions}
    }
    return LoadedState(guilds=guild_states, trivia=trivia)


async def load_guild_state(
    guild_id: int,
) -> tuple[GuildState | None, dict[str, list[QuestionData]]]:
    """Re-read a single guild (for live reloads). Returns ``(None, {})`` if the
    guild row no longer exists."""
    async with session_factory()() as s:
        g = (
            await s.execute(select(GuildRow).where(GuildRow.guild_id == guild_id))
        ).scalar_one_or_none()
        if g is None:
            return None, {}
        host_roles = (
            await s.execute(select(LfgHostRoleRow).where(LfgHostRoleRow.guild_id == guild_id))
        ).scalars().all()
        lfg_channels = (
            await s.execute(select(LfgChannelRow).where(LfgChannelRow.guild_id == guild_id))
        ).scalars().all()
        lfg_channel_roles = (
            await s.execute(
                select(LfgChannelRoleRow).where(LfgChannelRoleRow.guild_id == guild_id)
            )
        ).scalars().all()
        ga_channels = (
            await s.execute(
                select(GalatronChannelRow).where(GalatronChannelRow.guild_id == guild_id)
            )
        ).scalars().all()
        ga_attempts = (
            await s.execute(
                select(GalatronAttemptRow)
                .where(GalatronAttemptRow.guild_id == guild_id)
                .order_by(GalatronAttemptRow.occurred_at, GalatronAttemptRow.id)
            )
        ).scalars().all()
        ga_chances = (
            await s.execute(
                select(GalatronChanceRow).where(GalatronChanceRow.guild_id == guild_id)
            )
        ).scalars().all()
        tr_channels = (
            await s.execute(select(TriviaChannelRow).where(TriviaChannelRow.guild_id == guild_id))
        ).scalars().all()
        mc_channels = (
            await s.execute(
                select(MinecraftStatusChannelRow).where(
                    MinecraftStatusChannelRow.guild_id == guild_id
                )
            )
        ).scalars().all()
        tr_lists = (
            await s.execute(select(TriviaListRow).where(TriviaListRow.guild_id == guild_id))
        ).scalars().all()
        tr_questions = (
            await s.execute(
                select(TriviaQuestionRow)
                .where(TriviaQuestionRow.guild_id == guild_id)
                .order_by(TriviaQuestionRow.list_name, TriviaQuestionRow.local_id)
            )
        ).scalars().all()

    gs = _build_guild_state(
        g, host_roles, lfg_channels, lfg_channel_roles,
        ga_channels, ga_attempts, ga_chances, tr_channels, mc_channels,
    )
    return gs, _build_lists(tr_lists, tr_questions)
