from datetime import timedelta

import discord

from store.models import GalatronAttemptRow

from e2e.tests.helpers import (
    GALATRON_IMAGE, attempt, fail, galatron_text, pool_matches, register, setup_galatron, win,
)


async def test_attempt_before_setup_is_declined(e2e):
    response = await e2e.slash("attempt_galatron", user=e2e.players[0], in_channel=e2e.sandbox.galatron)
    assert "hasn't been set up" in response.original.content
    assert e2e.g.galatron_log.total_attempts == 0


async def test_attempt_outside_the_hunting_channel_is_declined(e2e):
    await setup_galatron(e2e)
    response = await e2e.slash("attempt_galatron", user=e2e.players[0], in_channel=e2e.sandbox.general)
    assert response.original.ephemeral
    assert pool_matches(galatron_text.WRONG_CHANNEL[register(e2e)], response.original.content)
    assert e2e.g.galatron_log.total_attempts == 0


async def test_failed_attempt_posts_a_short_line_and_sends_the_write_up_privately(e2e):
    await setup_galatron(e2e)
    player = e2e.players[0]
    voice = register(e2e)

    response = await fail(e2e, player)

    public, private = response.original, response.followups[0]
    assert not public.ephemeral and public.content.startswith("-# ")
    assert pool_matches(galatron_text.SHORT_FAIL[voice], public.content)
    assert private.ephemeral
    assert any(title in private.content for title in galatron_text.TITLES[f"{voice}/fail"].entries)
    assert public.files == [] and private.files == []

    assert e2e.g.galatron_log.total_for(player.id) == 1 and e2e.g.galatron_log.wins == []
    assert e2e.sandbox.galatron_role not in player.roles
    rows = await e2e.rows(GalatronAttemptRow, guild_id=e2e.guild.id)
    assert [(r.member_id, r.won) for r in rows] == [(player.id, False)]
    rebuilt = await e2e.assert_persisted(lambda g: g.galatron_log.total_for(player.id) == 1)
    assert str(rebuilt.galatron_register) == voice
    await e2e.assert_write_through()


async def test_win_is_announced_with_the_artwork(e2e):
    await setup_galatron(e2e)
    player = e2e.players[0]
    voice = register(e2e)

    response = await win(e2e, player)

    announcement = response.original
    assert not announcement.ephemeral
    assert announcement.filenames == ["galatron.png"]
    assert announcement.files[0].data == GALATRON_IMAGE.read_bytes()
    assert any(t in announcement.content for t in galatron_text.TITLES[f"{voice}/win"].entries)
    assert response.followups == []

    assert e2e.g.galatron_log.get_current_owner().id == player.id
    rebuilt = await e2e.assert_persisted(lambda g: len(g.galatron_log.wins) == 1)
    assert rebuilt.galatron_log.get_current_owner().id == player.id
    assert str(rebuilt.galatron_register) == str(e2e.g.galatron_register)
    await e2e.assert_write_through()


async def test_first_win_on_a_server_carries_the_first_bearer_line(e2e):
    await setup_galatron(e2e)
    response = await win(e2e, e2e.players[0])
    assert pool_matches(galatron_text.CONTEXTS["first_bearer"], response.original.content)


async def test_win_without_attach_files_is_sent_without_the_image(e2e):
    broken = e2e.sandbox.galatron_no_attach
    await e2e.slash("setting_set_galatron_role", role=e2e.sandbox.galatron_role)
    # the setup command refuses this channel; this is the permission being lost after setup
    await e2e.g.add_galatron_channel(broken)
    player = e2e.players[0]

    response = await win(e2e, player, channel=broken)

    assert response.original.files == []
    assert response.original.content
    assert any("Attach Files" in notice for _, notice in e2e.notices)
    assert e2e.g.galatron_log.get_current_owner().id == player.id


async def test_cooldown_rejects_then_expires(e2e):
    await setup_galatron(e2e)
    player = e2e.players[0]
    await fail(e2e, player)

    response = await attempt(e2e, player)
    assert response.original.ephemeral
    assert pool_matches(galatron_text.COOLDOWN[register(e2e)], response.original.content)
    next_allowed = int((e2e.g.galatron_log.last_attempt_at(player.id) + e2e.g.galatron_cooldown).timestamp())
    assert f"<t:{next_allowed}" in response.original.content
    assert e2e.g.galatron_log.total_for(player.id) == 1, "a rejection must not burn the attempt"

    e2e.advance_time(e2e.g.galatron_cooldown + timedelta(seconds=1))
    again = await fail(e2e, player)
    assert again.original.content.startswith("-# ")
    assert e2e.g.galatron_log.total_for(player.id) == 2
    await e2e.assert_persisted(lambda g: g.galatron_log.total_for(player.id) == 2)


async def test_custom_cooldown_is_what_expires(e2e):
    await setup_galatron(e2e)
    await e2e.slash("setting_set_galatron_cooldown", time_unit="minutes", time_amount=10)
    player = e2e.players[0]
    await fail(e2e, player)

    e2e.advance_time(timedelta(minutes=9))
    assert (await attempt(e2e, player)).original.ephemeral
    e2e.advance_time(timedelta(minutes=2))
    assert not (await fail(e2e, player)).original.ephemeral


async def test_the_bearer_cannot_claim_again(e2e):
    await setup_galatron(e2e)
    player = e2e.players[0]
    await win(e2e, player)
    e2e.advance_time(e2e.g.galatron_cooldown + timedelta(seconds=1))

    response = await attempt(e2e, player)
    assert response.original.ephemeral
    assert pool_matches(galatron_text.ALREADY_OWNER[register(e2e)], response.original.content)


async def test_role_moves_between_players_and_locate_follows(e2e):
    await setup_galatron(e2e)
    first, second = e2e.players[0], e2e.players[1]
    await win(e2e, first)
    assert e2e.sandbox.galatron_role in first.roles

    e2e.advance_time(timedelta(days=1, seconds=1))
    e2e.force_win()
    await attempt(e2e, second)
    await e2e.wait_for_role(second, e2e.sandbox.galatron_role)
    await e2e.wait_for_role(first, e2e.sandbox.galatron_role, present=False)

    assert e2e.g.galatron_log.get_current_owner().id == second.id
    located = await e2e.slash("locate_galatron", user=first, in_channel=e2e.sandbox.galatron)
    assert second.mention in located.original.content
    assert pool_matches(galatron_text.STATUS_TITLE[register(e2e)], located.original.content)
    await e2e.assert_write_through()


async def test_locate_without_bearer(e2e):
    await setup_galatron(e2e)
    response = await e2e.slash("locate_galatron", user=e2e.players[0], in_channel=e2e.sandbox.galatron)
    assert pool_matches(galatron_text.STATUS_UNBOUND[register(e2e)], response.original.content)


async def test_taking_it_back_mentions_the_revenge(e2e):
    await setup_galatron(e2e)
    first, second = e2e.players[0], e2e.players[1]
    await win(e2e, first)
    e2e.advance_time(timedelta(days=1, seconds=1))
    await win(e2e, second)

    e2e.advance_time(timedelta(days=2))
    e2e.force_all_contexts()
    response = await win(e2e, first)

    assert pool_matches(galatron_text.CONTEXTS["revenge"], response.original.content)
    assert second.mention in response.original.content


async def test_ending_a_record_reign_is_mentioned(e2e):
    await setup_galatron(e2e)
    first, second = e2e.players[0], e2e.players[1]
    await win(e2e, first)
    e2e.advance_time(timedelta(days=1, seconds=1))
    await win(e2e, second)

    e2e.advance_time(timedelta(days=8))
    e2e.force_all_contexts()
    response = await win(e2e, first)

    assert pool_matches(galatron_text.CONTEXTS["record_reign"], response.original.content)


async def test_first_win_of_a_member_on_a_server_with_history(e2e):
    await setup_galatron(e2e)
    first, second = e2e.players[0], e2e.players[1]
    await win(e2e, first)
    e2e.advance_time(timedelta(days=1, seconds=1))

    response = await win(e2e, second)

    assert pool_matches(galatron_text.CONTEXTS["first_win"], response.original.content)


async def test_bearer_leaving_announces_the_loss(e2e):
    await setup_galatron(e2e)
    bearer, other = e2e.players[0], e2e.players[1]
    await win(e2e, bearer)

    await e2e.member_remove(other)
    titles = {"The Bond is Severed", "Galatron Anchor Lost", "Breaker of the Chain"}

    def announced() -> list[discord.Message]:
        return [m for m in recent if m.embeds and m.embeds[0].title in titles]

    recent = await e2e.history(e2e.sandbox.galatron, 10)
    assert announced() == [], "someone without the role leaving must stay silent"

    await e2e.member_remove(bearer)
    recent = await e2e.history(e2e.sandbox.galatron, 10)
    assert len(announced()) == 1
    assert bearer.display_name in announced()[0].embeds[0].description


async def test_attempt_rows_use_the_clock(e2e):
    await setup_galatron(e2e)
    e2e.advance_time(timedelta(days=3))
    await fail(e2e, e2e.players[0])

    rows = await e2e.rows(GalatronAttemptRow, guild_id=e2e.guild.id)
    assert len(rows) == 1
    delta = rows[0].occurred_at.timestamp() - discord.utils.utcnow().timestamp()
    assert timedelta(days=2, hours=23) < timedelta(seconds=delta) < timedelta(days=3, minutes=5)
