"""Session wiring. Order matters: the e2e environment is loaded before anything of the bot is imported."""

from __future__ import annotations

import pytest
import pytest_asyncio

from e2e.harness.env import E2EConfigError, load_e2e_env, required_by_runner

try:
    CONFIG = load_e2e_env()
    CONFIG_ERROR = None
except E2EConfigError as exc:
    CONFIG = None
    CONFIG_ERROR = str(exc)


def pytest_report_header(config):
    if CONFIG is None:
        return f"e2e: NOT configured ({CONFIG_ERROR}); live tests are skipped"
    return f"e2e: guild {CONFIG.guild_id}, {len(CONFIG.dummy_user_ids)} dummy users, database host localhost"


def pytest_collection_modifyitems(config, items):
    for item in items:
        fixtures = getattr(item, "fixturenames", ())
        if ("e2e" in fixtures or "e2e_session" in fixtures) and "offline" not in item.keywords:
            item.add_marker(pytest.mark.e2e)


@pytest_asyncio.fixture(scope="session")
async def e2e_session():
    if CONFIG is None:
        message = f"e2e not configured: {CONFIG_ERROR}"
        if required_by_runner():
            pytest.fail(message, pytrace=False)
        pytest.skip(message)

    from e2e.harness import pycord
    from e2e.harness.bootstrap import start_bot
    from e2e.harness.core import E2E
    from e2e.harness.sandbox import Sandbox, purge_stale

    handle = await start_bot(CONFIG)
    bot = handle.bot
    gateway = pycord.InteractionGateway(bot)
    sandbox = None
    harness = None
    try:
        guild = bot.get_guild(CONFIG.guild_id)
        if guild is None:
            raise RuntimeError(f"the test bot is not in guild {CONFIG.guild_id}; invite it first (docs/testing.md)")

        dummies = []
        for user_id in CONFIG.dummy_user_ids:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            dummies.append(member)
        if dummies[1].guild_permissions.administrator:
            raise RuntimeError(
                f"the second dummy ({dummies[1]}) is already an administrator in the test guild, so it cannot act as "
                f"a plain member; put an admin bot first in E2E_DUMMY_USER_IDS"
            )

        pycord.demote_bot_admin(guild)

        async def keep_demoted(before, after):
            if after.guild.id == guild.id and after in guild.me.roles:
                pycord.demote_bot_admin(guild)

        bot.add_listener(keep_demoted, "on_guild_role_update")
        gateway.install()
        await purge_stale(guild)
        sandbox = Sandbox(guild, dummies)
        await sandbox.create()
        harness = E2E(bot, CONFIG, sandbox, gateway)
        yield harness
    finally:
        if harness is not None:
            await harness.close()
        gateway.uninstall()
        try:
            if sandbox is not None:
                await sandbox.teardown()
        finally:
            await handle.stop()


@pytest_asyncio.fixture
async def e2e(e2e_session):
    """The harness, reset to an empty configuration before every test."""
    await e2e_session.reset()
    yield e2e_session
