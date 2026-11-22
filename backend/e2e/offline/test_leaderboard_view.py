"""The leaderboard is a components v2 message: every page has to fit what discord enforces on one."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from classes.galatron_leaderboard_view import PAGE_SIZE, GalatronLeaderboardView
from classes.galatron_stats_view import GalatronStatsView
from e2e.harness import pycord

pytestmark = pytest.mark.offline


def entries(count: int):
    return [
        (SimpleNamespace(mention=f"<@{1000 + i}>"), timedelta(hours=count - i, seconds=i), i + 1) for i in range(count)
    ]


def payload(view: GalatronLeaderboardView) -> dict:
    return {"flags": pycord.IS_COMPONENTS_V2, "components": view.to_components()}


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 3, 4, PAGE_SIZE, PAGE_SIZE + 1, 3 * PAGE_SIZE + 4])
async def test_every_page_is_a_valid_v2_message_with_all_its_mentions(count):
    board = entries(count)
    view = GalatronLeaderboardView(SimpleNamespace(user=SimpleNamespace(id=1)), board, "Board")

    seen: list[str] = []
    for page in range(1, view.total_pages() + 1):
        view.current_page = page
        view.render()
        data = payload(view)
        assert pycord.validate_message(data) == [], f"page {page}"
        texts = pycord.component_texts(data["components"])
        assert any("Board" in t for t in texts)
        seen += [m.mention for m, _, _ in board if any(m.mention in t for t in texts)]
        assert view.prev_button.disabled == (page == 1)
        assert view.next_button.disabled == (page == view.total_pages())

    assert seen == [m.mention for m, _, _ in board], "every member appears exactly once across the pages"


@pytest.mark.asyncio
async def test_navigation_buttons_follow_the_page():
    view = GalatronLeaderboardView(SimpleNamespace(user=SimpleNamespace(id=1)), entries(25), "Board")
    assert view.prev_button.disabled and not view.next_button.disabled
    view.current_page = view.total_pages()
    view.render()
    assert not view.prev_button.disabled and view.next_button.disabled


def test_the_harness_rejects_what_discord_rejects_on_v2_messages():
    container = {"type": 17, "components": [{"type": 10, "content": "x" * 4001}]}
    problems = pycord.validate_message({"flags": pycord.IS_COMPONENTS_V2, "content": "hi", "components": [container]})
    assert any("content is not allowed" in p for p in problems)
    assert any("4001 characters" in p for p in problems)
    many = {"type": 17, "components": [{"type": 10, "content": "x"}] * 40}
    assert any("41 components" in p for p in pycord.validate_message({"flags": 1 << 15, "components": [many]}))


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 16, 40])
async def test_stats_pages_are_valid_v2_messages_with_all_their_mentions(count):
    stats = [(SimpleNamespace(mention=f"<@{1000 + i}>"), 5, 1, timedelta(minutes=i)) for i in range(count)]
    view = GalatronStatsView(SimpleNamespace(user=SimpleNamespace(id=1)), stats)

    texts: list[str] = []
    for page in range(1, view.total_pages() + 1):
        view.current_page = page
        view.render()
        data = payload(view)
        assert pycord.validate_message(data) == [], f"page {page}"
        texts += pycord.component_texts(data["components"])

    joined = "\n".join(texts)
    assert all(member.mention in joined for member, *_ in stats)
    if not count:
        assert "No data" in joined


@pytest.mark.asyncio
async def test_stats_leave_out_wins_and_duration_for_members_without_a_win():
    stats = [
        (SimpleNamespace(mention="<@1>"), 5, 2, timedelta(hours=3)),
        (SimpleNamespace(mention="<@2>"), 4, 0, timedelta()),
    ]
    view = GalatronStatsView(SimpleNamespace(user=SimpleNamespace(id=1)), stats)
    lines = pycord.component_texts(payload(view)["components"])[1].splitlines()

    assert "2 won" in lines[0]
    assert lines[1].endswith("<@2> · 4 tries")
