"""Every slash command of the real cogs can be turned into an interaction that py-cord accepts."""

from __future__ import annotations

import discord
import pytest
import pytest_asyncio

from e2e.harness import pycord
from e2e.offline import fakeguild

pytestmark = pytest.mark.offline


@pytest_asyncio.fixture
async def real(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@localhost/x")
    from classes import ServiceDroid, Settings
    from cogs.dev import DevelopmentCog
    from cogs.galatron_commands import GalatronCog
    from cogs.galatron_settings import GalatronSettingsCog
    from cogs.lfg_commands import LFGCog
    from cogs.lfg_settings import LFGSettingsCog
    from cogs.trivia_settings import TriviaSettingsCog

    bot = ServiceDroid(command_prefix="!", intents=discord.Intents.all(), settings=Settings())
    guild = fakeguild.build(bot)
    for cog in (GalatronCog, GalatronSettingsCog, LFGCog, LFGSettingsCog, DevelopmentCog, TriviaSettingsCog):
        bot.add_cog(cog(bot))
    for command in list(bot.pending_application_commands):
        command.guild_ids = None  # the dev cog is scoped to the real test guild when .env.e2e is loaded
        command.id = str(pycord.new_snowflake())
        bot._application_commands[command.id] = command
    return bot, guild


def sample(option: discord.Option, guild: discord.Guild):
    T = discord.SlashCommandOptionType
    if option.choices:
        return option.choices[0].value
    return {
        T.string: "x", T.integer: 1, T.number: 1.5, T.boolean: True,
        T.channel: guild.get_channel(fakeguild.GENERAL_ID),
        T.role: guild.get_role(fakeguild.ADMIN_ROLE_ID),
        T.user: guild.get_member(fakeguild.PLAYER_ID),
    }[option.input_type]


async def test_every_command_builds_a_payload_py_cord_accepts(real):
    bot, guild = real
    member = guild.get_member(fakeguild.ADMIN_ID)
    channel = guild.get_channel(fakeguild.GENERAL_ID)
    commands = [c for c in bot.application_commands if isinstance(c, discord.SlashCommand)]
    assert len(commands) > 30

    for command in commands:
        options = {o.name: sample(o, guild) for o in command.options}
        payload, leaf, _ = pycord.build_command_payload(
            bot, f"{pycord.TOKEN_PREFIX}probe", guild, channel, member, (command.name,), options,
        )
        interaction = discord.Interaction(data=payload, state=bot._connection)
        assert interaction.command is None and interaction.data["name"] == command.name
        assert interaction.user.id == member.id and interaction.guild_id == guild.id
        assert leaf is command
