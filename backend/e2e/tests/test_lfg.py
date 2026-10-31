from datetime import timedelta


async def setup_lfg(e2e, host_cooldown_hours: int = 1):
    sandbox = e2e.sandbox
    await e2e.slash("setting_set_host", role=sandbox.lfg_host_role, time_unit="hours", time_amount=host_cooldown_hours)
    await e2e.slash("setting_add_lfg", channel=sandbox.lfg, role=sandbox.lfg_ping_role)
    host = e2e.players[1]
    await host.add_roles(sandbox.lfg_host_role)
    await e2e.wait_for_role(host, sandbox.lfg_host_role)
    return host


async def invite(e2e, host, channel=None):
    return await e2e.slash("lfg", user=host, in_channel=channel or e2e.sandbox.lfg, text="anyone up for a round?")


async def test_settings_are_persisted(e2e):
    sandbox = e2e.sandbox
    response = await e2e.slash("setting_set_host", role=sandbox.lfg_host_role, time_unit="hours", time_amount=1)
    assert "has been set to 1 hours" in response.original.content
    await e2e.assert_persisted(lambda g: g.host_roles[sandbox.lfg_host_role.id].get_cooldown_text() == "1 hours")

    same = await e2e.slash("setting_set_host", role=sandbox.lfg_host_role, time_unit="hours", time_amount=1)
    assert "Nothing changed" in same.original.content

    blocked = await e2e.slash("setting_set_host", role=sandbox.lfg_host_role, time_unit="hours", time_amount=0)
    assert "can't use LFG commands anymore" in blocked.original.content

    added = await e2e.slash("setting_add_lfg", channel=sandbox.lfg, role=sandbox.lfg_ping_role)
    assert "is now a LFG Channel" in added.original.content
    again = await e2e.slash("setting_add_lfg", channel=sandbox.lfg, role=sandbox.lfg_ping_role)
    assert "already being mentioned" in again.original.content
    await e2e.assert_persisted(
        lambda g: [r.id for r in g.lfg_channels[sandbox.lfg.id].roles] == [sandbox.lfg_ping_role.id]
    )

    shown = await e2e.slash("current_settings_lfg")
    assert sandbox.lfg.mention in shown.original.text and sandbox.lfg_ping_role.mention in shown.original.text
    await e2e.assert_write_through()

    await e2e.slash("setting_remove_lfg", channel=sandbox.lfg)
    await e2e.slash("setting_remove_host", role=sandbox.lfg_host_role)
    await e2e.assert_persisted(lambda g: not g.lfg_channels and not g.host_roles)
    await e2e.assert_write_through()


async def test_invite_is_posted_then_the_cooldown_applies_until_the_clock_passes_it(e2e):
    host = await setup_lfg(e2e)

    first = await invite(e2e, host)
    assert first.original.ephemeral and first.original.deleted, "the placeholder reply is removed again"
    posted = (await e2e.history(e2e.sandbox.lfg, 5))
    invites = [m for m in posted if m.content.startswith(f"{host.mention} is looking for a game!")]
    assert invites and e2e.sandbox.lfg_ping_role.mention in invites[0].content
    assert "anyone up for a round?" in invites[0].content

    second = await invite(e2e, host)
    assert second.original.ephemeral and "still on cooldown" in second.original.content

    e2e.advance_time(timedelta(minutes=59))
    assert "still on cooldown" in (await invite(e2e, host)).original.content

    e2e.advance_time(timedelta(minutes=2))
    third = await invite(e2e, host)
    assert "still on cooldown" not in third.original.content and third.original.deleted


async def test_reset_cooldown_command_frees_the_member(e2e):
    host = await setup_lfg(e2e)
    await invite(e2e, host)
    assert "still on cooldown" in (await invite(e2e, host)).original.content

    response = await e2e.slash("reset_cooldown", member=host)
    assert "has been reset" in response.original.content
    assert "still on cooldown" not in (await invite(e2e, host)).original.content

    nobody = await e2e.slash("reset_cooldown", member=e2e.admin)
    assert "isn't on cooldown" in nobody.original.content

    await invite(e2e, host)
    everyone = await e2e.slash("reset_cooldown")
    assert "All cooldowns have been reset" in everyone.original.content
    assert "still on cooldown" not in (await invite(e2e, host)).original.content


async def test_members_without_a_host_role_and_wrong_channels_are_declined(e2e):
    host = await setup_lfg(e2e)

    no_role = await e2e.slash("lfg", user=e2e.admin, in_channel=e2e.sandbox.lfg)
    assert "don't posses any roles" in no_role.original.content

    elsewhere = await invite(e2e, host, channel=e2e.sandbox.general)
    assert "isn't allowed here" in elsewhere.original.content


async def test_missing_channel_permissions_notify_the_owner(e2e):
    sandbox = e2e.sandbox
    host = e2e.players[1]
    await e2e.slash("setting_set_host", role=sandbox.lfg_host_role, time_unit="hours", time_amount=1)
    await host.add_roles(sandbox.lfg_host_role)
    await e2e.wait_for_role(host, sandbox.lfg_host_role)
    # the setup command would refuse this channel; the permission is gone after setup
    await e2e.g.add_lfg_role(sandbox.galatron_no_send, sandbox.lfg_ping_role)

    response = await invite(e2e, host, channel=sandbox.galatron_no_send)

    assert "missing permissions" in response.original.content
    assert any("can't post LFG invites" in notice for _, notice in e2e.notices)


async def test_setup_refuses_a_channel_the_bot_cannot_write_in(e2e):
    response = await e2e.slash("setting_add_lfg", channel=e2e.sandbox.galatron_no_send, role=e2e.sandbox.lfg_ping_role)
    assert "Send Messages" in response.original.content
    assert e2e.g.lfg_channels == {}
