from store.models import MinecraftStatusChannelRow


async def test_mirroring_a_server_is_persisted_and_renames_the_channel(e2e):
    e2e.mock_minecraft(online=3)
    channel = e2e.sandbox.voice

    response = await e2e.slash("setting_minecraft_set_channel", channel=channel, address="mc.example.test")

    assert response.original.ephemeral
    assert "**3** player(s) online" in response.original.content
    assert channel.mention in response.original.content
    assert [(r.channel_id, r.address) for r in await e2e.rows(MinecraftStatusChannelRow, guild_id=e2e.guild.id)] == [
        (channel.id, "mc.example.test")
    ]
    await e2e.assert_persisted(lambda g: g.minecraft_channels[channel.id].address == "mc.example.test")
    await e2e.assert_write_through()

    # asked through REST: in one run the rename happened at once but the cached channel never showed it
    async def renamed() -> bool:
        return await e2e.channel_name(channel) == "🟢 Online: 3"

    await e2e.eventually(renamed, "channel renamed to the status", timeout=20, interval=1.0)

    shown = await e2e.slash("setting_minecraft_show_mappings")
    assert f"<#{channel.id}>" in shown.original.text and "mc.example.test" in shown.original.text

    removed = await e2e.slash("setting_minecraft_remove_channel", channel=channel)
    assert "no longer mirrors" in removed.original.content
    await e2e.assert_persisted(lambda g: g.minecraft_channels == {})
    assert channel.id not in e2e.bot.minecraft_updater._tasks

    again = await e2e.slash("setting_minecraft_remove_channel", channel=channel)
    assert "is not mirroring" in again.original.content


async def test_unreachable_server_is_reported(e2e):
    e2e.mock_minecraft(online=None)
    channel = await e2e.sandbox.voice_channel("mc-offline")

    response = await e2e.slash("setting_minecraft_set_channel", channel=channel, address="down.example.test")

    assert "not reachable" in response.original.content
    await e2e.assert_persisted(lambda g: channel.id in g.minecraft_channels)


async def test_setup_validates_address_and_bot_permissions(e2e):
    e2e.mock_minecraft(online=1)

    blank = await e2e.slash("setting_minecraft_set_channel", channel=e2e.sandbox.voice, address=" ")
    assert "must not be empty" in blank.original.content

    refused = await e2e.slash(
        "setting_minecraft_set_channel", channel=e2e.sandbox.voice_no_manage, address="mc.example.test",
    )
    assert "Manage Channels" in refused.original.content and refused.original.ephemeral
    assert e2e.g.minecraft_channels == {}

    empty = await e2e.slash("setting_minecraft_show_mappings")
    assert "No Minecraft status channels" in empty.original.content
