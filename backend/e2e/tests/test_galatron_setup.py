from store.models import GalatronAttemptRow

from e2e.tests.helpers import setup_galatron


async def test_channel_setup_happy_path_is_persisted(e2e):
    channel = e2e.sandbox.galatron
    response = await e2e.slash("setting_add_galatron_channel", channel=channel)
    assert "is now viable" in response.original.content
    assert response.original.ephemeral

    assert [c.id for c in e2e.g.galatron_channels] == [channel.id]
    await e2e.assert_persisted(lambda g: [c.id for c in g.galatron_channels] == [channel.id])

    again = await e2e.slash("setting_add_galatron_channel", channel=channel)
    assert "already being used" in again.original.content

    await e2e.slash("setting_remove_galatron_channel", channel=channel)
    assert e2e.g.galatron_channels == []
    await e2e.assert_persisted(lambda g: g.galatron_channels == [])


async def test_channel_setup_checks_attach_files(e2e):
    channel = e2e.sandbox.galatron_no_attach
    response = await e2e.slash("setting_add_galatron_channel", channel=channel)

    assert response.original.ephemeral
    assert "Attach Files" in response.original.content
    assert channel.mention in response.original.content
    assert "Send Messages" not in response.original.content
    assert e2e.g.galatron_channels == []
    await e2e.assert_persisted(lambda g: g.galatron_channels == [])


async def test_channel_setup_checks_send_messages(e2e):
    response = await e2e.slash("setting_add_galatron_channel", channel=e2e.sandbox.galatron_no_send)
    assert "Send Messages" in response.original.content
    assert e2e.g.galatron_channels == []


async def test_role_setup_is_persisted_and_validated(e2e):
    role = e2e.sandbox.galatron_role
    response = await e2e.slash("setting_set_galatron_role", role=role)
    assert "is now being used" in response.original.content
    assert e2e.g.galatron_role.id == role.id
    await e2e.assert_persisted(lambda g: g.galatron_role is not None and g.galatron_role.id == role.id)

    again = await e2e.slash("setting_set_galatron_role", role=role)
    assert "already being used" in again.original.content

    everyone = await e2e.slash("setting_set_galatron_role", role=e2e.guild.default_role)
    assert "@everyone" in everyone.original.content and everyone.original.ephemeral
    assert e2e.g.galatron_role.id == role.id

    managed = await e2e.slash("setting_set_galatron_role", role=e2e.guild.me.top_role)
    assert managed.original.ephemeral
    assert "managed by an integration" in managed.original.content
    assert e2e.g.galatron_role.id == role.id


async def test_chance_setting(e2e):
    chance = await e2e.slash("setting_set_galatron_chance", chance=50.0)
    assert "50.0% chance is now" in chance.original.content
    assert e2e.g.galatron_chance == 0.5
    await e2e.assert_persisted(lambda g: g.galatron_chance == 0.5)

    bad = await e2e.slash("setting_set_galatron_chance", chance=150.0)
    assert "between 0 and 100" in bad.original.content
    assert e2e.g.galatron_chance == 0.5

    await e2e.assert_write_through()


async def test_current_settings_embed_shows_the_configuration(e2e):
    await setup_galatron(e2e)
    response = await e2e.slash("current_settings_galatron")
    text = response.original.text
    assert e2e.sandbox.galatron.mention in text
    assert e2e.sandbox.galatron_role.mention in text
    assert "Cooldown" in text and "Chance" in text


async def test_wipe_clears_attempts_everywhere(e2e):
    await setup_galatron(e2e)
    e2e.force_fail()
    await e2e.slash("attempt_galatron", user=e2e.players[0], in_channel=e2e.sandbox.galatron)
    assert len(await e2e.rows(GalatronAttemptRow, guild_id=e2e.guild.id)) == 1

    response = await e2e.slash("galatron_reset")
    assert "reset complete" in response.original.content

    assert e2e.g.galatron_log.total_attempts == 0
    assert await e2e.rows(GalatronAttemptRow, guild_id=e2e.guild.id) == []
    await e2e.assert_persisted(lambda g: g.galatron_log.total_attempts == 0)
    await e2e.assert_write_through()
