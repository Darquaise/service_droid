"""Harness self-tests: the synthetic interaction layer against an in-memory guild, no Discord, no DB."""

from __future__ import annotations

import pytest

from e2e.harness import pycord
from e2e.offline import fakeguild

pytestmark = pytest.mark.offline


async def run(fake, *path, user=None, channel=None, **options):
    return await fake.gateway.run_command(
        guild=fake.guild, channel=channel or fake.general, member=user or fake.player,
        path=path, options=options,
    )


async def test_plain_reply_is_captured(fake):
    response = await run(fake, "hello")
    assert response.original.content == "hello there"
    assert response.original.ephemeral
    assert response.callback_type == pycord.RESP_CHANNEL_MESSAGE


async def test_all_option_kinds_reach_the_callback_converted(fake):
    role = fake.guild.get_role(fakeguild.ADMIN_ROLE_ID)
    response = await run(
        fake, "kinds", user=fake.admin, who=fake.player, where=fake.quiet, what=role, count=3, unit="days",
    )
    assert response.original.content == (
        f"{fake.player.id}|{fake.quiet.id}|{role.id}|3|0.5|days"
    )
    assert response.original.embeds[0].description == f"by {fake.admin.id}"
    assert not response.original.ephemeral


async def test_default_member_permissions_are_enforced_like_discord(fake):
    with pytest.raises(pycord.CommandNotAvailable):
        await run(
            fake, "kinds", user=fake.player, who=fake.player, where=fake.general,
            what=fake.guild.default_role, count=1,
        )


async def test_unknown_and_missing_options_fail_loudly(fake):
    with pytest.raises(pycord.HarnessError, match="missing required option"):
        await run(fake, "kinds", user=fake.admin)
    with pytest.raises(pycord.HarnessError, match="unknown option"):
        await run(fake, "hello", nonsense=1)
    with pytest.raises(pycord.HarnessError, match="not one of"):
        await run(
            fake, "kinds", user=fake.admin, who=fake.player, where=fake.general,
            what=fake.guild.default_role, count=1, unit="weeks",
        )


async def test_defer_then_followups(fake):
    response = await run(fake, "slow")
    assert response.callback_type == pycord.RESP_DEFERRED_CHANNEL_MESSAGE
    assert [m.kind for m in response.messages] == ["original", "followup"]
    assert response.original.content == "first answer" and response.original.ephemeral
    assert response.followups[0].content == "second answer" and not response.followups[0].ephemeral
    assert not response.original.loading


async def test_files_are_captured_with_their_bytes(fake):
    response = await run(fake, "file")
    assert response.original.filenames == ["a.txt"]
    assert response.original.files[0].data == b"abc"


async def test_edit_original_response(fake):
    response = await run(fake, "later")
    assert response.original.content == "after"
    assert response.original.edits == 1


async def test_button_click_updates_the_message_in_place(fake):
    response = await run(fake, "pager")
    message = response.view_message
    assert message.component("next").kind == "button"

    click = await fake.gateway.run_component(
        guild=fake.guild, channel=fake.general, member=fake.player,
        message=message, component=message.component("next"),
    )
    assert message.content == "page 2"
    assert message.edits == 1
    assert click.source is message
    assert "page 2" in click.text


async def test_click_by_somebody_else_is_ignored_by_the_view(fake):
    response = await run(fake, "pager")
    message = response.view_message
    click = await fake.gateway.run_component(
        guild=fake.guild, channel=fake.general, member=fake.admin,
        message=message, component=message.component("next"),
    )
    assert click.callback_type == pycord.RESP_DEFERRED_UPDATE
    assert message.content == "page 1"


async def test_select_values(fake):
    response = await run(fake, "pick")
    message = response.view_message
    select = next(c for c in message.components if c.kind == "select")
    assert select.options == ["a", "b"]
    await fake.gateway.run_component(
        guild=fake.guild, channel=fake.general, member=fake.player,
        message=message, component=select, values=["b"],
    )
    assert message.content == "picked b"
    assert message.components == []


async def test_a_failing_command_is_reported(fake):
    with pytest.raises(pycord.CommandFailed) as caught:
        await run(fake, "boom")
    assert isinstance(caught.value.errors[0], RuntimeError)

    response = await fake.gateway.run_command(
        guild=fake.guild, channel=fake.general, member=fake.player, path=("boom",), options={},
        expect_error=True,
    )
    assert response.errors


async def test_stale_component_is_rejected(fake):
    response = await run(fake, "pager")
    message = response.view_message
    component = message.component("next")
    fake.bot._connection._view_store._views.clear()
    with pytest.raises(pycord.HarnessError, match="no view is registered"):
        await fake.gateway.run_component(
            guild=fake.guild, channel=fake.general, member=fake.player, message=message, component=component,
        )


async def test_bot_admin_demotion_lets_channel_overwrites_count(fake):
    me = fake.guild.me
    assert fake.quiet.permissions_for(me).attach_files  # administrator bypasses the overwrite
    pycord.demote_bot_admin(fake.guild)
    assert not fake.quiet.permissions_for(me).attach_files
    assert fake.general.permissions_for(me).attach_files
    assert me.guild_permissions.manage_roles and not me.guild_permissions.administrator
