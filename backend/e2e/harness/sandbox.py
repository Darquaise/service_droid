"""The throw-away part of the test guild: one category with channels and roles per run.

Everything is named ``e2e-<run>-...``; ``purge_stale`` removes what a crashed earlier run left behind.
Some channels are deliberately broken for the bot (real permission overwrites). The bot is an
administrator in Discord, so these only bite because ``pycord.demote_bot_admin`` strips that from its
local permission view.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import discord

logger = logging.getLogger(__name__)

PREFIX = "e2e-"
# younger leftovers may belong to a run on another machine that is still going
STALE_AFTER = timedelta(minutes=30)


class Sandbox:
    def __init__(self, guild: discord.Guild, dummies: list[discord.Member]):
        self.guild = guild
        self.dummies = dummies
        self.run_id = secrets.token_hex(3)
        self.name = f"{PREFIX}{self.run_id}"
        self._channels: list[discord.abc.GuildChannel] = []
        self._roles: list[discord.Role] = []

        self.category: discord.CategoryChannel
        self.general: discord.TextChannel
        self.log: discord.TextChannel
        self.galatron: discord.TextChannel
        self.galatron_other: discord.TextChannel
        self.galatron_no_attach: discord.TextChannel
        self.galatron_no_send: discord.TextChannel
        self.lfg: discord.TextChannel
        self.trivia: discord.TextChannel
        self.trivia_no_embed: discord.TextChannel
        self.voice: discord.VoiceChannel
        self.voice_no_manage: discord.VoiceChannel
        self.galatron_role: discord.Role
        self.admin_role: discord.Role
        self.lfg_host_role: discord.Role
        self.lfg_ping_role: discord.Role

    # -- creation ---------------------------------------------------------------------------

    async def create(self) -> None:
        guild = self.guild
        me = guild.me
        self.category = await guild.create_category(self.name, reason="e2e run")
        self._channels.append(self.category)

        def deny(**perms) -> dict:
            return {me: discord.PermissionOverwrite(**perms)}

        self.general = await self.text("general")
        self.log = await self.text("log")
        self.galatron = await self.text("galatron")
        self.galatron_other = await self.text("galatron-other")
        self.galatron_no_attach = await self.text("galatron-no-attach", deny(attach_files=False))
        self.galatron_no_send = await self.text("galatron-no-send", deny(send_messages=False))
        self.lfg = await self.text("lfg")
        self.trivia = await self.text("trivia")
        self.trivia_no_embed = await self.text("trivia-no-embed", deny(embed_links=False))
        self.voice = await self.voice_channel("mc")
        self.voice_no_manage = await self.voice_channel("mc-no-manage", deny(manage_channels=False))

        self.galatron_role = await self.role("galatron")
        self.lfg_host_role = await self.role("lfg-host")
        self.lfg_ping_role = await self.role("lfg-ping", mentionable=True)
        self.admin_role = await self.role("admin", permissions=discord.Permissions(administrator=True))
        await self.dummies[0].add_roles(self.admin_role, reason="e2e admin")
        await self.eventually(lambda: self.admin_role in self.dummies[0].roles, "admin role on dummy 0")

    async def text(self, name: str, overwrites: dict | None = None) -> discord.TextChannel:
        channel = await self.guild.create_text_channel(
            f"{self.name}-{name}", category=self.category, overwrites=overwrites or {}, reason="e2e run",
        )
        self._channels.append(channel)
        return channel

    async def voice_channel(self, name: str, overwrites: dict | None = None) -> discord.VoiceChannel:
        channel = await self.guild.create_voice_channel(
            f"{self.name}-{name}", category=self.category, overwrites=overwrites or {}, reason="e2e run",
        )
        self._channels.append(channel)
        return channel

    async def role(self, name: str, **kwargs) -> discord.Role:
        role = await self.guild.create_role(name=f"{self.name}-{name}", reason="e2e run", **kwargs)
        self._roles.append(role)
        await self.eventually(lambda: self.guild.get_role(role.id) is not None, f"role {name} in cache")
        return role

    # -- teardown ---------------------------------------------------------------------------

    async def teardown(self) -> None:
        for dummy in self.dummies:
            for role in self._roles:
                if role in dummy.roles:
                    await _quietly(dummy.remove_roles(role, reason="e2e teardown"))
        for channel in reversed(self._channels):
            await _quietly(channel.delete(reason="e2e teardown"))
        for role in self._roles:
            await _quietly(role.delete(reason="e2e teardown"))
        self._channels.clear()
        self._roles.clear()

    # -- helpers ----------------------------------------------------------------------------

    @staticmethod
    async def eventually(
            predicate: Callable[[], Any], what: str = "condition", timeout: float = 10.0, interval: float = 0.05,
    ) -> None:
        """The gateway cache catches up with REST changes a moment later; poll until it has.
        ``predicate`` may be async (e.g. a REST fetch) — then pick an ``interval`` that respects rate limits."""
        deadline = time.monotonic() + timeout
        while True:
            result = predicate()
            if inspect.isawaitable(result):
                result = await result
            if result:
                return
            if time.monotonic() > deadline:
                raise TimeoutError(f"timed out waiting for {what}")
            await asyncio.sleep(interval)


async def purge_stale(guild: discord.Guild) -> None:
    """Remove ``e2e-*`` categories, their channels and ``e2e-*`` roles that a crashed run left over."""
    cutoff = datetime.now(timezone.utc) - STALE_AFTER

    def stale(obj: discord.abc.Snowflake) -> bool:
        return obj.name.startswith(PREFIX) and obj.created_at < cutoff

    for category in list(guild.categories):
        if stale(category):
            for channel in list(category.channels):
                await _quietly(channel.delete(reason="e2e stale cleanup"))
            await _quietly(category.delete(reason="e2e stale cleanup"))
    for channel in list(guild.channels):
        if stale(channel) and not isinstance(channel, discord.CategoryChannel):
            await _quietly(channel.delete(reason="e2e stale cleanup"))
    for role in list(guild.roles):
        if stale(role):
            await _quietly(role.delete(reason="e2e stale cleanup"))


async def _quietly(awaitable) -> None:
    try:
        await awaitable
    except discord.NotFound:
        pass
    except discord.HTTPException:
        logger.exception("e2e cleanup call failed")
