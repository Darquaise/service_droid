from datetime import timedelta

from e2e.tests.helpers import attempt, fail, galatron_text, pool_matches, register, setup_galatron, win


async def test_empty_leaderboard_and_stats(e2e):
    await setup_galatron(e2e)
    user = e2e.players[0]
    voice = register(e2e)

    board = await e2e.slash("galatron_leaderboard", user=user, in_channel=e2e.sandbox.galatron)
    assert pool_matches(galatron_text.NO_LEADERBOARD[voice], board.original.content)

    total = await e2e.slash("galatron_stats_total", user=user, in_channel=e2e.sandbox.galatron)
    assert pool_matches(galatron_text.NO_ATTEMPTS[voice], total.original.content)

    stats = await e2e.slash("galatron_stats", user=user, in_channel=e2e.sandbox.galatron)
    assert "No data" in stats.original.text


async def test_stats_commands_only_work_in_the_hunting_channel(e2e):
    await setup_galatron(e2e)
    for command in ("galatron_leaderboard", "galatron_stats", "galatron_stats_total"):
        response = await e2e.slash(command, user=e2e.players[0], in_channel=e2e.sandbox.general)
        assert response.original.ephemeral, command
        assert pool_matches(galatron_text.WRONG_CHANNEL[register(e2e)], response.original.content), command


async def test_leaderboard_primes_the_mentions_then_shows_embeds(e2e):
    await setup_galatron(e2e)
    bearer = e2e.players[0]
    await win(e2e, bearer)

    response = await e2e.slash("galatron_leaderboard", user=bearer, in_channel=e2e.sandbox.galatron)

    message = response.original
    assert message.edits == 1, "mentions are posted first, then edited into embeds"
    assert message.content == ""
    assert "Galatron Leaderboard" in message.embeds[0].title
    assert bearer.mention in message.embeds[0].description
    assert message.component("⬅️").disabled and message.component("➡️").disabled


async def test_stats_table_lists_everyone_who_tried(e2e):
    await setup_galatron(e2e)
    first, second = e2e.players[0], e2e.players[1]
    await win(e2e, first)
    await fail(e2e, second)

    response = await e2e.slash("galatron_stats", user=first, in_channel=e2e.sandbox.galatron)

    text = response.original.text
    assert first.name in text and second.name in text
    assert "Tries" in text and "Success" in text


async def test_total_stats_use_the_chance_of_their_time(e2e):
    await setup_galatron(e2e)
    player = e2e.players[0]
    await fail(e2e, player)

    e2e.advance_time(timedelta(days=1, seconds=1))
    await e2e.slash("setting_set_galatron_chance", chance=50.0)
    e2e.advance_time(timedelta(seconds=2))
    await fail(e2e, player)

    response = await e2e.slash("galatron_stats_total", user=player, in_channel=e2e.sandbox.galatron)

    text = response.original.text
    assert "**Total uses:** 2 (by 1 individuals)" in text
    assert "**Total received:** 0" in text
    assert "0.5% (1×)" in text and "50% (1×)" in text
    await e2e.assert_write_through()


async def test_attempts_of_two_players_are_counted_per_individual(e2e):
    await setup_galatron(e2e)
    await fail(e2e, e2e.players[0])
    await fail(e2e, e2e.players[1])
    # a rejected attempt inside the cooldown must not show up
    await attempt(e2e, e2e.players[0])

    response = await e2e.slash("galatron_stats_total", user=e2e.players[0], in_channel=e2e.sandbox.galatron)
    assert "**Total uses:** 2 (by 2 individuals)" in response.original.text
