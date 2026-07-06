from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
import discord
from mcstatus import JavaServer

if TYPE_CHECKING:
    from .bot import ServiceDroid

logger = logging.getLogger(__name__)

UPDATE_INTERVAL = 330
OFFLINE_AFTER_FAILS = 2
PING_TIMEOUT = 10

STATUS_ONLINE = "🟢 Online: {count}"
STATUS_RESTARTING = "🟠 Restarting"
STATUS_OFFLINE = "🔴 Offline"


def _log(msg: str) -> None:
    logger.info("[minecraft] %s", msg)


async def fetch_player_count(address: str) -> int | None:
    try:
        server = await JavaServer.async_lookup(address)
        status = await asyncio.wait_for(server.async_status(), timeout=PING_TIMEOUT)
        return status.players.online
    except asyncio.CancelledError:
        raise
    except Exception:
        return None


class MinecraftStatusConfig:
    __slots__ = ("channel_id", "address", "was_online", "fail_count")

    def __init__(self, channel_id: int, address: str):
        self.channel_id = channel_id
        self.address = address
        # runtime-only ping tracking (not persisted)
        self.was_online = False
        self.fail_count = 0

    def status_name(self, online: int | None) -> str:
        if online is not None:
            self.was_online = True
            self.fail_count = 0
            return STATUS_ONLINE.format(count=online)
        self.fail_count += 1
        if self.was_online and self.fail_count <= OFFLINE_AFTER_FAILS:
            return STATUS_RESTARTING
        self.was_online = False
        return STATUS_OFFLINE


class MinecraftStatusUpdater:
    __slots__ = ("bot", "_tasks")

    def __init__(self, bot: "ServiceDroid"):
        self.bot = bot
        self._tasks: dict[int, asyncio.Task] = {}

    def schedule_channel(self, channel_id: int, config: MinecraftStatusConfig) -> None:
        self.cancel_channel(channel_id)
        task = self.bot.loop.create_task(
            self._loop_for_channel(channel_id, config),
            name=f"minecraft-status-{channel_id}",
        )
        self._tasks[channel_id] = task

    def cancel_channel(self, channel_id: int) -> None:
        task = self._tasks.pop(channel_id, None)
        if task is not None and not task.done():
            task.cancel()

    def cancel_all(self) -> None:
        for cid in list(self._tasks):
            self.cancel_channel(cid)

    async def _loop_for_channel(self, channel_id: int, config: MinecraftStatusConfig) -> None:
        try:
            while True:
                try:
                    await self._update_once(channel_id, config)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    _log(f"channel {channel_id}: error updating status: {e!r}")
                await asyncio.sleep(UPDATE_INTERVAL)
        except asyncio.CancelledError:
            pass

    async def _update_once(self, channel_id: int, config: MinecraftStatusConfig) -> None:
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            _log(f"channel {channel_id}: not accessible or not a voice channel, skipping")
            return

        online = await fetch_player_count(config.address)
        name = config.status_name(online)
        if channel.name == name:
            return
        try:
            await channel.edit(name=name, reason=f"Minecraft status: {config.address}")
        except discord.Forbidden:
            _log(f"channel {channel_id}: missing Manage Channels permission, cannot rename")
        except discord.HTTPException as e:
            _log(f"channel {channel_id}: failed to rename: {e!r}")
