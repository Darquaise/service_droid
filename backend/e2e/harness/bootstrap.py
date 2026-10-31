"""Start the real bot inside the test event loop, the way ``main.py`` does."""

from __future__ import annotations

import asyncio
import logging

import discord

from .env import E2EConfig

logger = logging.getLogger(__name__)

STARTUP_TIMEOUT = 120.0


class BotHandle:
    def __init__(self, bot: discord.Bot, task: asyncio.Task):
        self.bot = bot
        self.task = task

    async def stop(self) -> None:
        await self.bot.close()
        try:
            await asyncio.wait_for(self.task, timeout=30)
        except RuntimeError:
            # py-cord's reconnect loop races close() and hits the already closed aiohttp session
            pass
        except (asyncio.TimeoutError, asyncio.CancelledError, discord.DiscordException):
            logger.warning("bot task did not end cleanly")


async def start_bot(config: E2EConfig) -> BotHandle:
    # imported here: cogs/dev.py reads DEBUG_GUILD_IDS at import time, so the env must be loaded first
    from classes import ServiceDroid, Settings
    from cogs.startup import StartupCog
    from logging_setup import setup_logging

    setup_logging()
    settings = Settings()
    bot = ServiceDroid(
        command_prefix=settings.command_prefix,
        case_insensitive=True,
        help_command=None,
        debug_guilds=settings.debug_guild_ids if settings.debug else None,
        intents=discord.Intents.all(),
        settings=settings,
        owner_ids=set(settings.owner_ids),
    )
    bot.exit_code = 0
    bot.add_cog(StartupCog(bot))

    task = asyncio.create_task(bot.start(config.token), name="e2e-bot")
    ready = asyncio.create_task(bot.startup_complete.wait())
    try:
        done, _ = await asyncio.wait({task, ready}, timeout=STARTUP_TIMEOUT, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise TimeoutError(f"bot did not finish startup within {STARTUP_TIMEOUT:.0f}s")
        if task in done:
            task.result()
            raise RuntimeError("bot stopped during startup (see log: startup failed?)")
    except BaseException:
        ready.cancel()
        await bot.close()
        task.cancel()
        raise
    return BotHandle(bot, task)
