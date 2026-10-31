from __future__ import annotations

import pytest_asyncio

import discord

from e2e.harness import pycord
from e2e.offline import fakeguild
from e2e.offline.fakecog import FakeCog


@pytest_asyncio.fixture
async def fake():
    """A bot with an in-memory guild, a small cog and the interaction gateway installed (no Discord)."""
    bot = discord.Bot(intents=discord.Intents.all(), auto_sync_commands=False)
    guild = fakeguild.build(bot)
    cog = FakeCog()
    bot.add_cog(cog)
    for command in list(bot.pending_application_commands):
        command.id = str(pycord.new_snowflake())
        bot._application_commands[command.id] = command

    gateway = pycord.InteractionGateway(bot)
    gateway.install()
    try:
        yield type("Fake", (), {"bot": bot, "guild": guild, "cog": cog, "gateway": gateway,
                                "general": guild.get_channel(fakeguild.GENERAL_ID),
                                "quiet": guild.get_channel(fakeguild.QUIET_ID),
                                "admin": guild.get_member(fakeguild.ADMIN_ID),
                                "player": guild.get_member(fakeguild.PLAYER_ID)})()
    finally:
        gateway.uninstall()
