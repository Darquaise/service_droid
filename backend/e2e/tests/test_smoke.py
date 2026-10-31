async def test_status_answers(e2e):
    response = await e2e.slash("status")
    assert response.original.content == "Bot is here!"
    assert response.original.ephemeral
    assert response.errors == []


async def test_the_answer_was_mirrored_for_inspection(e2e):
    response = await e2e.slash("status")
    await e2e.flush_mirrors()
    mirror = response.original.mirror
    assert mirror is not None
    assert "Bot is here!" in mirror.content and "/status" in mirror.content
