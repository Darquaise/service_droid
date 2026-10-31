import pytest

from classes.permissions import DISSOLVE_AFTER_PERM_FAILS
from classes.trivia import TriviaChannelConfig

from e2e.harness.pycord import CommandNotAvailable
from e2e.tests.helpers import add_list, add_question, attempt, galatron_text, setup_galatron

ADMIN_ONLY_PREFIXES = ("setting_", "current_settings_", "commands_")
ADMIN_ONLY_NAMES = {
    "galatron_reset", "reset_cooldown", "status", "restart", "shutdown", "reload", "log", "list_guilds",
}


def test_admin_commands_are_gated_and_player_commands_are_not(e2e_session):
    for command in e2e_session.bot.application_commands:
        needed = command.default_member_permissions
        if command.name.startswith(ADMIN_ONLY_PREFIXES) or command.name in ADMIN_ONLY_NAMES:
            assert needed is not None and needed.administrator, f"/{command.name} must require Administrator"
        else:
            assert needed is None, f"/{command.name} is a player command and must not be gated"


async def test_a_plain_member_cannot_reach_admin_commands(e2e):
    await setup_galatron(e2e)
    e2e.force_fail()
    await attempt(e2e, e2e.players[0])

    with pytest.raises(CommandNotAvailable):
        await e2e.slash("galatron_reset", user=e2e.member)
    with pytest.raises(CommandNotAvailable):
        await e2e.slash("setting_set_galatron_chance", user=e2e.member, chance=100.0)
    with pytest.raises(CommandNotAvailable):
        await e2e.slash("status", user=e2e.member)

    assert e2e.g.galatron_log.total_attempts == 1
    assert e2e.g.galatron_chance != 1.0
    await e2e.assert_write_through()


async def test_setup_commands_name_every_missing_permission(e2e):
    response = await e2e.slash("setting_add_galatron_channel", channel=e2e.sandbox.galatron_no_send)

    text = response.original.content
    assert "missing the following permissions" in text
    for label in ("Send Messages", "Embed Links", "Attach Files"):
        assert label in text
    assert e2e.sandbox.galatron_no_send.mention in text


async def test_galatron_is_suspended_when_the_role_cannot_be_handed_out(e2e):
    await e2e.slash("setting_add_galatron_channel", channel=e2e.sandbox.galatron)
    # the setting command refuses @everyone; this is the role turning unassignable after setup
    await e2e.g.set_galatron_role(e2e.guild.default_role)

    response = await attempt(e2e, e2e.players[0])

    assert response.original.ephemeral
    assert response.original.content in galatron_text.SUSPENDED.entries
    assert any("Galatron hunt is broken" in notice for _, notice in e2e.notices)
    assert e2e.g.galatron_log.total_attempts == 0, "a suspended attempt must not be recorded"


async def test_trivia_is_dissolved_after_repeated_permission_failures(e2e):
    await add_list(e2e)
    await add_question(e2e)
    channel = e2e.sandbox.trivia_no_embed
    config = TriviaChannelConfig(channel.id, "mix", "0 20 * * *", 5)
    # the setup command refuses this channel; this is the permission being lost after setup
    await e2e.g.set_trivia_channel(config)
    scheduler = e2e.bot.trivia_scheduler

    for _ in range(DISSOLVE_AFTER_PERM_FAILS):
        await scheduler._fire(channel.id, config)
        await e2e.eventually(lambda: channel.id not in scheduler._perm_failures, "failure handling", timeout=10)

    warnings = [n for _, n in e2e.notices if "couldn't post trivia" in n]
    disabled = [n for _, n in e2e.notices if "disabled trivia" in n]
    # the warning text is identical every time, so notify_owner's deduplication lets only the first through
    assert len(warnings) == 1 and len(disabled) == 1
    assert "Embed Links" in disabled[0]
    assert channel.id not in e2e.g.trivia_channels
    await e2e.assert_persisted(lambda g: channel.id not in g.trivia_channels)
