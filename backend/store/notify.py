from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
import psycopg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CHANNEL = "sd_changes"

# Identifies this process; lets the listener ignore notifications it caused.
ORIGIN = uuid.uuid4().hex


async def emit_change(session: AsyncSession, guild_id: int) -> None:
    payload = json.dumps({"guild_id": guild_id, "origin": ORIGIN})
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": CHANNEL, "payload": payload},
    )


def _libpq_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


class ChangeListener:
    def __init__(self, database_url: str, on_change: Callable[[int], Awaitable[None]]):
        self._url = _libpq_url(database_url)
        self._on_change = on_change
        self._task: asyncio.Task | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._task is None:
            self._task = loop.create_task(self._run(), name="db-change-listener")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self._listen_forever()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("change listener connection failed (%r); retrying in 5s", e)
                await asyncio.sleep(5)

    async def _listen_forever(self) -> None:
        aconn = await psycopg.AsyncConnection.connect(self._url, autocommit=True)
        try:
            await aconn.execute(f"LISTEN {CHANNEL}")
            logger.info("listening for external database changes on '%s'", CHANNEL)
            async for note in aconn.notifies():
                await self._handle(note.payload)
        finally:
            await aconn.close()

    async def _handle(self, payload: str) -> None:
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            logger.warning("ignoring malformed change payload: %r", payload)
            return
        if data.get("origin") == ORIGIN:
            return  # bot write gets skipped
        guild_id = data.get("guild_id")
        if not isinstance(guild_id, int):
            return
        try:
            await self._on_change(guild_id)
        except Exception:
            logger.exception("reload after external change for guild %s failed", guild_id)
