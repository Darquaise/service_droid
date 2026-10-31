from __future__ import annotations

from classes import galatron_text
from cogs.galatron_commands import GALATRON_IMAGE
from e2e.harness.core import E2E, pool_matches

__all__ = [
    "GALATRON_IMAGE", "PICK", "add_list", "add_question", "attempt", "bind", "fail", "galatron_text",
    "pool_matches", "register", "setup_galatron", "win",
]

PICK = "Pick a list..."


async def setup_galatron(e2e: E2E, channel=None) -> None:
    """Role and hunting channel configured through the real settings commands."""
    channel = channel or e2e.sandbox.galatron
    e2e.keep_clear_of_daily_reset()
    await e2e.slash("setting_set_galatron_role", role=e2e.sandbox.galatron_role)
    await e2e.slash("setting_add_galatron_channel", channel=channel)


def register(e2e: E2E) -> str:
    return str(e2e.g.galatron_register)


async def attempt(e2e: E2E, user, channel=None):
    return await e2e.slash("attempt_galatron", user=user, in_channel=channel or e2e.sandbox.galatron)


async def win(e2e: E2E, user, channel=None):
    e2e.force_win()
    response = await attempt(e2e, user, channel)
    await e2e.wait_for_role(user, e2e.sandbox.galatron_role)
    return response


async def fail(e2e: E2E, user, channel=None):
    e2e.force_fail()
    return await attempt(e2e, user, channel)


async def add_list(e2e: E2E, name: str = "mix") -> None:
    response = await e2e.slash("setting_trivia_list_add", name=name)
    assert "has been created" in response.original.content


async def add_question(
        e2e: E2E, list_name: str = "mix", title: str = "Capital", question: str = "Capital of France?",
        answer: str = "Paris", context: str = "",
):
    options = {"title": title, "question": question, "answer": answer}
    if context:
        options["answer_context"] = context
    response = await e2e.slash("setting_trivia_add", **options)
    done = await e2e.select(response, PICK, list_name)
    assert "added to list" in done.source.content
    return done


async def bind(
        e2e: E2E, channel=None, list_name: str = "mix", schedule: str = "0 20 * * *", response: int = 2, **extra,
):
    channel = channel or e2e.sandbox.trivia
    prompt = await e2e.slash(
        "setting_trivia_set_channel", channel=channel, schedule=schedule, response=response, **extra,
    )
    return await e2e.select(prompt, PICK, list_name)
