"""The ``e2e`` object tests talk to. Public API only; py-cord internals stay in ``pycord.py``."""

from __future__ import annotations

import asyncio
import io
import logging
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable

import discord

from .env import E2EConfig
from .pycord import (
    CapturedMessage, HarnessError, InteractionGateway, Response, _resolve_command, required_permissions,
)
from .sandbox import Sandbox

logger = logging.getLogger(__name__)

MIRROR_LIMIT = 2000
MIRROR_HEADER = "-# e2e"


class E2E:
    def __init__(
            self, bot: discord.Bot, config: E2EConfig, sandbox: Sandbox, gateway: InteractionGateway,
    ):
        self.bot = bot
        self.config = config
        self.sandbox = sandbox
        self.gateway = gateway
        gateway.mirror = self._mirror

        self.guild: discord.Guild = sandbox.guild
        self.players: list[discord.Member] = sandbox.dummies
        self.admin: discord.Member = sandbox.dummies[0]
        self.member: discord.Member = sandbox.dummies[1]
        self.notices: list[tuple[int, str]] = []
        self._undo: list[Callable[[], None]] = []
        self._dm_patches: list[tuple[type, str, Any]] = []
        self._test_started = discord.utils.time_snowflake(datetime.now(timezone.utc))
        self._mirror_queue: asyncio.Queue[tuple[CapturedMessage, str]] = asyncio.Queue()
        self._mirror_worker = asyncio.create_task(self._mirror_loop(), name="e2e-mirror")
        self._install_notice_capture()

    # -- invoking ---------------------------------------------------------------------------

    async def slash(
            self, *path: str, user: discord.Member | None = None, in_channel: discord.abc.GuildChannel | None = None,
            enforce_permissions: bool = True, expect_error: bool = False, timeout: float = 30.0,
            **options: Any,
    ) -> Response:
        """Run ``/path...`` as ``user`` in ``in_channel`` with ``options`` and return what the bot answered.

        ``user`` defaults to the admin dummy for commands that need default_member_permissions and to
        ``e2e.member`` for all others. ``in_channel`` defaults to ``sandbox.general`` (it is not called
        ``channel`` because several commands have an option of that name). With
        ``enforce_permissions`` the member must hold the command's default_member_permissions, as
        Discord itself would require before sending the interaction.
        """
        if not path:
            raise HarnessError("slash() needs the command name")
        if user is None:
            _, chain = _resolve_command(self.bot, self.guild, path)
            user = self.admin if required_permissions(chain) is not None else self.member
        return await self.gateway.run_command(
            guild=self.guild, channel=in_channel or self.sandbox.general, member=user, path=path,
            options=options, enforce_permissions=enforce_permissions, expect_error=expect_error, timeout=timeout,
        )

    async def click(
            self, target: Response | CapturedMessage, ident: str, *, user: discord.Member | None = None,
            expect_error: bool = False, timeout: float = 30.0,
    ) -> Response:
        """Press the button ``ident`` (custom_id, else label) on a response/message.

        The click comes from whoever ran the command unless ``user`` says otherwise.
        """
        message, member = self._component_target(target, user)
        return await self.gateway.run_component(
            guild=self.guild, channel=self._channel_of(message), member=member, message=message,
            component=message.component(ident), expect_error=expect_error, timeout=timeout,
        )

    async def select(
            self, target: Response | CapturedMessage, ident: str, *values: str,
            user: discord.Member | None = None, expect_error: bool = False, timeout: float = 30.0,
    ) -> Response:
        """Choose ``values`` in the select menu ``ident`` (custom_id, else placeholder)."""
        message, member = self._component_target(target, user)
        component = message.component(ident)
        if component.kind != "select":
            raise HarnessError(f"{ident!r} is a {component.kind}, not a select")
        bad = [v for v in values if v not in component.options]
        if bad:
            raise HarnessError(f"{bad} are not options of {ident!r}; has {component.options}")
        return await self.gateway.run_component(
            guild=self.guild, channel=self._channel_of(message), member=member, message=message,
            component=component, values=list(values), expect_error=expect_error, timeout=timeout,
        )

    def _component_target(
            self, target: Response | CapturedMessage, user: discord.Member | None,
    ) -> tuple[CapturedMessage, discord.Member]:
        if isinstance(target, Response):
            message = target.view_message
            if message is None:
                raise HarnessError(f"{target!r} has no message with components")
            return message, user or target.user
        return target, user or target.interaction.user

    def _channel_of(self, message: CapturedMessage) -> discord.abc.GuildChannel:
        channel = self.guild.get_channel(message.channel_id)
        assert channel is not None
        return channel

    # -- time and randomness ----------------------------------------------------------------

    def advance_time(self, delta: timedelta) -> None:
        """Move the bot's clock (classes/clock.py) forward. Real sleeps and gateway timing are unaffected."""
        from classes import clock
        clock.advance(delta)

    def advance_to_daily_reset(self) -> None:
        """Move the clock one second past the next 00:00 UTC, when the Galatron cooldown lifts for everyone."""
        from classes import clock
        from classes.galatron import next_reset
        clock.advance(next_reset(clock.now_utc()) - clock.now_utc() + timedelta(seconds=1))

    def keep_clear_of_daily_reset(self, margin: timedelta = timedelta(minutes=30)) -> None:
        """A test running across the real 00:00 UTC would see its cooldown lift mid-way; if that is
        closer than ``margin``, jump past it first."""
        from classes import clock
        from classes.galatron import next_reset
        if next_reset(clock.now_utc()) - clock.now_utc() < margin:
            self.advance_to_daily_reset()

    def force_random(self, *values: float) -> None:
        """Make ``random.random()`` in cogs/galatron_commands return ``values`` in turn (the last one
        repeats). The win roll is ``random.random() < chance``, so ``0.0`` wins and ``0.999`` loses."""
        from cogs import galatron_commands
        if not values:
            raise HarnessError("force_random needs at least one value")
        queue = list(values)

        def roll() -> float:
            return queue.pop(0) if len(queue) > 1 else queue[0]

        self._set(galatron_commands, "random", SimpleNamespace(random=roll))

    def force_win(self) -> None:
        self.force_random(0.0)

    def force_fail(self) -> None:
        self.force_random(0.999)

    def force_all_contexts(self) -> None:
        """Make every Galatron context line whose condition holds actually appear (their own chance rolls pass)."""
        from classes import galatron_text
        self._set(galatron_text.rng, "random", lambda: 0.0)

    def patch(self, owner: Any, name: str, value: Any) -> None:
        """Replace ``owner.name`` until the next test."""
        self._set(owner, name, value)

    def _set(self, owner: Any, name: str, value: Any) -> None:
        had = name in vars(owner)
        old = vars(owner).get(name)
        setattr(owner, name, value)

        def undo() -> None:
            if had:
                setattr(owner, name, old)
            else:
                delattr(owner, name)

        self._undo.append(undo)

    def mock_minecraft(self, online: int | None) -> None:
        """Answer every Minecraft status ping with ``online`` players (``None`` = unreachable)."""
        from classes import minecraft

        class FakeServer:
            async def async_status(self_inner):
                if online is None:
                    raise OSError("e2e: server unreachable")
                return SimpleNamespace(players=SimpleNamespace(online=online))

        async def lookup(address: str, *args, **kwargs):
            return FakeServer()

        self._set(minecraft.JavaServer, "async_lookup", staticmethod(lookup))

    # -- bot state --------------------------------------------------------------------------

    @property
    def g(self):
        """The live in-memory ``Guild`` of the test guild."""
        from classes import Guild
        g = Guild.get(self.guild.id)
        assert g is not None
        return g

    def cog(self, name: str):
        cog = self.bot.get_cog(name)
        assert cog is not None, f"no cog {name}"
        return cog

    async def eventually(
            self, predicate: Callable[[], Any], what: str = "condition", timeout: float = 10.0, interval: float = 0.05,
    ) -> None:
        """Poll until the gateway cache reflects a REST change (role added, ...). ``predicate`` may be async."""
        await Sandbox.eventually(predicate, what, timeout, interval)

    async def channel_name(self, channel: discord.abc.GuildChannel) -> str:
        """The name Discord itself reports, bypassing the gateway cache."""
        return (await self.guild.fetch_channel(channel.id)).name

    async def wait_for_role(self, member: discord.Member, role: discord.Role, present: bool = True) -> None:
        await self.eventually(lambda: (role in member.roles) == present, f"{role.name} {'on' if present else 'off'} {member}")

    async def history(self, channel: discord.abc.Messageable, limit: int = 10) -> list[discord.Message]:
        """What the bot really posted in a channel during the current test, newest first (mirrors excluded)."""
        messages = [
            m async for m in channel.history(limit=100, after=discord.Object(self._test_started), oldest_first=False)
            if not m.content.startswith(MIRROR_HEADER)
        ]
        return messages[:limit]

    async def member_remove(self, member: discord.Member) -> None:
        """Run the bot's ``on_member_remove`` listener with a real Member (the dummies are never kicked)."""
        await self.cog("EventsCog").on_member_remove(member)

    # -- persistence ------------------------------------------------------------------------

    async def rebuilt_guild(self):
        """A ``Guild`` built from what is in the database right now, without touching the live registry."""
        from classes import Guild
        from classes.base.guildbase import GuildBase
        from store import load_state

        state = await load_state()
        live = GuildBase._instances.get(self.guild.id)
        try:
            return Guild.from_state(self.guild, state.guilds.get(self.guild.id))
        finally:
            # from_state registers the new object; put the live one back
            if live is not None:
                GuildBase._instances[self.guild.id] = live
            else:
                GuildBase._instances.pop(self.guild.id, None)

    async def assert_persisted(self, predicate: Callable[[Any], Any], message: str = "") -> Any:
        """Rebuild the guild from the database and assert ``predicate(rebuilt_guild)`` — proof that the
        change was written through, not only held in memory. ``predicate`` may be async."""
        rebuilt = await self.rebuilt_guild()
        result = predicate(rebuilt)
        if asyncio.iscoroutine(result):
            result = await result
        assert result, message or f"not persisted: {getattr(predicate, '__name__', predicate)} is false on the rebuilt guild"
        return rebuilt

    async def assert_write_through(self) -> None:
        """The live guild and a guild rebuilt from the database agree on all persisted fields."""
        rebuilt = await self.rebuilt_guild()
        live, stored = guild_snapshot(self.g), guild_snapshot(rebuilt)
        diff = {k: (live[k], stored[k]) for k in live if live[k] != stored[k]}
        assert not diff, f"memory and database disagree (live, stored): {diff}"

        from classes import TriviaHandler
        from store import load_state
        handler = TriviaHandler.get(self.guild.id)
        live_lists = trivia_snapshot(handler.lists) if handler else {}
        stored_lists = {
            name: [(q.local_id, q.title, list(q.question), q.answer, q.answer_context) for q in questions]
            for name, questions in (await load_state()).trivia.get(self.guild.id, {}).items()
        }
        assert live_lists == stored_lists, f"trivia lists disagree (live, stored): {live_lists} / {stored_lists}"

    async def rows(self, model: type, **filters: Any) -> list:
        """Rows of a ``store.models`` table, e.g. ``await e2e.rows(GalatronAttemptRow, guild_id=...)``."""
        from sqlalchemy import select
        from store import session_factory

        async with session_factory()() as session:
            return list((await session.execute(select(model).filter_by(**filters))).scalars().all())

    # -- per-test reset ---------------------------------------------------------------------

    async def reset(self) -> None:
        """Back to an empty configuration: database rows of the guild, in-memory state, clock, patches,
        roles held by the dummies. Tests set up their own state through commands afterwards."""
        from classes import clock, galatron_text, permissions, reload_guild
        from store import guild_repo

        await self.flush_mirrors()
        while self._undo:
            self._undo.pop()()
        clock.reset()
        galatron_text.Pool._recent.clear()
        galatron_text.rng.seed(1234)
        permissions._notified.clear()
        self.notices.clear()
        self.gateway.by_token.clear()
        self.gateway.by_interaction_id.clear()
        self.cog("LFGCog").cooldowns.clear()

        scheduler = self.bot.trivia_scheduler
        if scheduler is not None:
            scheduler.cancel_all()
        updater = self.bot.minecraft_updater
        if updater is not None:
            updater.cancel_all()

        await self._wipe_database()
        await guild_repo.ensure_guilds([(self.guild.id, self.guild.name)])
        await reload_guild(self.bot, self.guild.id)
        joined_at = self.guild.me.joined_at
        if joined_at is not None:
            await self.g.ensure_galatron_timelines(joined_at)

        self._test_started = discord.utils.time_snowflake(datetime.now(timezone.utc))
        for member in self.players:
            for role in self.sandbox._roles:
                if role is not self.sandbox.admin_role and role in member.roles:
                    await member.remove_roles(role, reason="e2e reset")
                    await self.wait_for_role(member, role, present=False)

    async def _wipe_database(self) -> None:
        from sqlalchemy import text
        from store import session_factory

        channel_ids = [c.id for c in self.guild.channels]
        async with session_factory()() as session, session.begin():
            # everything else hangs off guild with ON DELETE CASCADE
            await session.execute(text("DELETE FROM guild WHERE guild_id = :g"), {"g": self.guild.id})
            await session.execute(
                text("DELETE FROM trivia_pending WHERE channel_id = ANY(:ids)"), {"ids": channel_ids},
            )

    # -- owner notices ----------------------------------------------------------------------

    def _install_notice_capture(self) -> None:
        """Swallow every DM: tests must never message a real person. ``notify_owner`` itself runs for real
        (deduplication included); what it would DM the owner lands in ``notices``."""
        harness = self

        async def captured_dm(target, content=None, *args, **kwargs):
            text = str(content or "")
            prefix = f"**{harness.guild.name}**\n"
            if text.startswith(prefix):
                harness.notices.append((harness.guild.id, text[len(prefix):]))
            else:
                logger.warning("e2e: swallowed a DM to %s: %r", target, text[:200])

        for cls in (discord.Member, discord.User):
            self._dm_patches.append((cls, "send", vars(cls).get("send", _MISSING)))
            cls.send = captured_dm

    async def close(self) -> None:
        await self.flush_mirrors()
        self._mirror_worker.cancel()
        for cls, name, original in self._dm_patches:
            if original is _MISSING:
                delattr(cls, name)
            else:
                setattr(cls, name, original)
        self._dm_patches.clear()

    # -- mirroring --------------------------------------------------------------------------

    async def _mirror(self, record: CapturedMessage, event: str) -> None:
        # queued: a real channel.send (rate limits included) must not delay the bot's answer
        self._mirror_queue.put_nowait((record, event))

    async def flush_mirrors(self) -> None:
        await self._mirror_queue.join()

    async def _mirror_loop(self) -> None:
        while True:
            record, event = await self._mirror_queue.get()
            try:
                await self._post_mirror(record, event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("mirroring %s of %r failed", event, record)
            finally:
                self._mirror_queue.task_done()

    async def _post_mirror(self, record: CapturedMessage, event: str) -> None:
        """Post what the bot answered as a real message so a human can read the run afterwards."""
        origin = self.guild.get_channel(record.channel_id)
        channel = origin
        me = self.guild.me
        if not isinstance(channel, discord.TextChannel) or not channel.permissions_for(me).send_messages:
            channel = self.sandbox.log

        header = f"{MIRROR_HEADER} · `/{record.interaction.command}` · {record.interaction.user.display_name}"
        tags = [record.kind]
        if record.ephemeral:
            tags.append("ephemeral")
        if channel is not origin:
            tags.append(f"in #{getattr(origin, 'name', record.channel_id)}")
        if record.components:
            tags.append("components: " + ", ".join(str(c.label or c.custom_id) for c in record.components))
        if event == "edit":
            tags.append(f"edit {record.edits}")
        if record.deleted:
            tags.append("deleted")
        header += " · " + " · ".join(tags)

        body = record.content[: MIRROR_LIMIT - len(header) - 2]
        content = f"{header}\n{body}" if body else header
        perms = channel.permissions_for(me)
        embeds = record.embeds if perms.embed_links else []

        if record.mirror is None:
            files = (
                [discord.File(io.BytesIO(f.data), filename=f.filename) for f in record.files]
                if perms.attach_files else []
            )
            record.mirror = await channel.send(
                content=content, embeds=embeds, files=files, allowed_mentions=discord.AllowedMentions.none(),
            )
        else:
            await record.mirror.edit(content=content, embeds=embeds, allowed_mentions=discord.AllowedMentions.none())


_MISSING = object()


# -- snapshots ------------------------------------------------------------------------------

def _ts(dt) -> float:
    return round(dt.timestamp(), 3)


def guild_snapshot(g) -> dict:
    """Every persisted field of a ``Guild`` in a comparable shape."""
    return {
        "galatron_role": g.galatron_role.id if g.galatron_role else None,
        "galatron_channels": sorted(c.id for c in g.galatron_channels),
        "galatron_register": str(g.galatron_register),
        "galatron_chances": [(_ts(t), v) for t, v in g.galatron_chances.periods],
        "galatron_attempts": [(a.member_id, _ts(a.occurred_at), a.won) for a in g.galatron_log.attempts],
        "host_roles": {rid: h.get_cooldown_text() for rid, h in sorted(g.host_roles.items())},
        "lfg_channels": {
            cid: sorted(r.id for r in ch.roles) for cid, ch in sorted(g.lfg_channels.items())
        },
        "trivia_channels": {
            cid: (c.list_name, c.schedule, c.response, c.mode, c.order, c.next_index_value)
            for cid, c in sorted(g.trivia_channels.items())
        },
        "minecraft_channels": {cid: c.address for cid, c in sorted(g.minecraft_channels.items())},
    }


def trivia_snapshot(lists: dict) -> dict:
    return {
        name: [(q.id, q.title, list(q.question), q.answer, q.answer_context) for q in questions]
        for name, questions in lists.items()
    }


def pool_matches(pool, text: str) -> bool:
    """True if ``text`` contains one of the lines of a galatron_text ``Pool``; ``{placeholders}`` match anything."""
    for entry in pool.entries:
        pattern = re.sub(r"\\\{\w+\\\}", ".+?", re.escape(entry))
        if re.search(pattern, text, re.DOTALL):
            return True
    return False
