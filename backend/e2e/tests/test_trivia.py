import asyncio
from datetime import timedelta
from types import SimpleNamespace

from classes import clock, trivia_scheduler

from store.models import TriviaPendingRow

from e2e.tests.helpers import PICK, add_list, add_question, bind

async def test_lists_and_questions_are_persisted(e2e):
    await add_list(e2e)
    again = await e2e.slash("setting_trivia_list_add", name="mix")
    assert "already exists" in again.original.content

    await add_question(e2e)
    await add_question(e2e, title="Rivers", question="Longest river?", answer="Nile", context="Probably")

    shown = await e2e.slash("setting_trivia_list")
    assert "**mix** — 2 questions" in shown.original.text
    await e2e.assert_write_through()

    wording = await e2e.slash("setting_trivia_add_variation", trivia_id=1, wording="France's capital?")
    done = await e2e.select(wording, PICK, "mix")
    assert "2 wordings total" in done.source.content

    removal = await e2e.slash("setting_trivia_remove", trivia_id=2)
    gone = await e2e.select(removal, PICK, "mix")
    assert "removed from list" in gone.source.content
    await e2e.assert_write_through()

    listing = await e2e.slash("setting_trivia_list_show")
    page = await e2e.select(listing, PICK, "mix")
    assert "Capital" in page.source.text and "Rivers" not in page.source.text


async def test_removing_a_list_in_use_is_refused(e2e):
    await add_list(e2e)
    await add_question(e2e)
    await bind(e2e)

    prompt = await e2e.slash("setting_trivia_list_remove")
    refused = await e2e.select(prompt, PICK, "mix")
    assert "still being used" in refused.source.content

    await e2e.slash("setting_trivia_reset_channel", channel=e2e.sandbox.trivia)
    prompt = await e2e.slash("setting_trivia_list_remove")
    removed = await e2e.select(prompt, PICK, "mix")
    assert "has been deleted" in removed.source.content
    await e2e.assert_write_through()


async def test_channel_binding_is_persisted_and_updatable(e2e):
    await add_list(e2e)
    await add_question(e2e)

    bound = await bind(e2e, schedule="*/30 * * * *", response=45)
    assert "is now bound to list **mix**" in bound.source.content
    channel_id = e2e.sandbox.trivia.id
    await e2e.assert_persisted(
        lambda g: (g.trivia_channels[channel_id].schedule, g.trivia_channels[channel_id].response)
        == ("*/30 * * * *", 45)
    )
    assert channel_id in e2e.bot.trivia_scheduler._question_tasks, "binding starts the channel's loop"

    await e2e.slash("setting_trivia_update_schedule", channel=e2e.sandbox.trivia, schedule="0 18 * * 5")
    await e2e.slash("setting_trivia_update_response", channel=e2e.sandbox.trivia, response=90)
    await e2e.assert_persisted(
        lambda g: (g.trivia_channels[channel_id].schedule, g.trivia_channels[channel_id].response)
        == ("0 18 * * 5", 90)
    )

    shown = await e2e.slash("setting_trivia_show_mappings")
    assert f"<#{channel_id}>" in shown.original.text and "0 18 * * 5" in shown.original.text

    bad = await e2e.slash("setting_trivia_update_schedule", channel=e2e.sandbox.trivia, schedule="nonsense")
    assert "not a valid cron expression" in bad.original.content
    zero = await e2e.slash("setting_trivia_update_response", channel=e2e.sandbox.trivia, response=0)
    assert "greater than 0" in zero.original.content
    await e2e.assert_write_through()

    await e2e.slash("setting_trivia_reset_channel", channel=e2e.sandbox.trivia)
    await e2e.assert_persisted(lambda g: g.trivia_channels == {})
    assert channel_id not in e2e.bot.trivia_scheduler._question_tasks


async def test_binding_validates_input_and_channel_permissions(e2e):
    await add_list(e2e)

    cron = await e2e.slash("setting_trivia_set_channel", channel=e2e.sandbox.trivia, schedule="bad", response=5)
    assert "not a valid cron expression" in cron.original.content

    seconds = await e2e.slash(
        "setting_trivia_set_channel", channel=e2e.sandbox.trivia, schedule="0 20 * * *", response=0,
    )
    assert "greater than 0" in seconds.original.content

    embed = await e2e.slash(
        "setting_trivia_set_channel", channel=e2e.sandbox.trivia_no_embed, schedule="0 20 * * *", response=5,
    )
    assert "Embed Links" in embed.original.content
    assert e2e.g.trivia_channels == {}


async def test_a_question_and_its_timed_answer(e2e):
    await add_list(e2e)
    await add_question(e2e, context="Since the tenth century.")
    await bind(e2e, response=2)
    channel = e2e.sandbox.trivia
    config = e2e.g.trivia_channels[channel.id]
    scheduler = e2e.bot.trivia_scheduler

    await scheduler._fire(channel.id, config)

    question = (await e2e.history(channel, 1))[0].embeds[0]
    assert question.title == "Trivia: Capital"
    assert question.description == "Capital of France?"
    assert question.footer.text == "Answer in 2s"
    assert config.pending is not None
    rows = await e2e.rows(TriviaPendingRow, channel_id=channel.id)
    assert [r.answer for r in rows] == ["Paris"]

    await e2e.eventually(lambda: config.pending is None, "answer reveal", timeout=15)
    answer = (await e2e.history(channel, 1))[0].embeds[0]
    assert answer.title == "Answer: Capital"
    assert "**Paris**" in answer.description and "Since the tenth century." in answer.description
    assert await e2e.rows(TriviaPendingRow, channel_id=channel.id) == []


async def test_sequential_order_advances_and_persists(e2e):
    await add_list(e2e)
    await add_question(e2e, title="One", question="first?", answer="1")
    await add_question(e2e, title="Two", question="second?", answer="2")
    await bind(e2e, response=1, order="sequential")
    channel = e2e.sandbox.trivia
    config = e2e.g.trivia_channels[channel.id]
    scheduler = e2e.bot.trivia_scheduler

    await scheduler._fire(channel.id, config)
    await e2e.eventually(lambda: config.pending is None, "first reveal", timeout=15)
    await scheduler._fire(channel.id, config)
    await e2e.eventually(lambda: config.pending is None, "second reveal", timeout=15)

    titles = [m.embeds[0].title for m in reversed(await e2e.history(channel, 4))]
    assert titles == ["Trivia: One", "Answer: One", "Trivia: Two", "Answer: Two"]
    await e2e.assert_persisted(lambda g: g.trivia_channels[channel.id].next_index_value == 2)


async def test_the_loop_sleeps_until_the_next_cron_tick_of_the_clock(e2e):
    await add_list(e2e)
    await add_question(e2e)
    await bind(e2e, schedule="0 20 * * *")
    channel = e2e.sandbox.trivia
    config = e2e.g.trivia_channels[channel.id]
    scheduler = e2e.bot.trivia_scheduler
    scheduler.cancel_channel(channel.id)

    sleeps: list[float] = []
    fired = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError
        e2e.advance_time(timedelta(seconds=seconds))

    async def fire(self, channel_id, cfg) -> None:
        fired.append(clock.now_utc())

    e2e.patch(trivia_scheduler, "asyncio", SimpleNamespace(**{**vars(asyncio), "sleep": sleep}))
    e2e.patch(type(scheduler), "_fire", fire)
    await scheduler._loop_for_channel(channel.id, config)

    assert len(fired) == 1 and (fired[0].hour, fired[0].minute) == (20, 0)
    assert abs(sleeps[1] - 86400) < 5, "after a tick the loop waits for the same time on the next day"


async def test_a_pending_answer_whose_time_has_passed_is_discarded(e2e):
    await add_list(e2e)
    await add_question(e2e)
    await bind(e2e, response=3600)
    channel = e2e.sandbox.trivia
    config = e2e.g.trivia_channels[channel.id]
    scheduler = e2e.bot.trivia_scheduler

    await scheduler._fire(channel.id, config)
    assert config.pending is not None
    scheduler.cancel_all()  # the "restart": the pending row stays behind
    assert len(await e2e.rows(TriviaPendingRow, channel_id=channel.id)) == 1

    e2e.advance_time(timedelta(hours=2))
    await scheduler._deliver_pending(channel.id, config)

    assert config.pending is None
    assert await e2e.rows(TriviaPendingRow, channel_id=channel.id) == []
    assert (await e2e.history(channel, 1))[0].embeds[0].title == "Trivia: Capital", "no late answer was posted"


async def test_a_pending_answer_still_in_the_future_is_delivered_after_a_restart(e2e):
    await add_list(e2e)
    await add_question(e2e)
    await bind(e2e, response=2)
    channel = e2e.sandbox.trivia
    config = e2e.g.trivia_channels[channel.id]
    scheduler = e2e.bot.trivia_scheduler

    await scheduler._fire(channel.id, config)
    scheduler.cancel_all()
    await asyncio.sleep(0.1)

    await scheduler._deliver_pending(channel.id, config)

    assert (await e2e.history(channel, 1))[0].embeds[0].title == "Answer: Capital"
    assert config.pending is None
    assert await e2e.rows(TriviaPendingRow, channel_id=channel.id) == []
