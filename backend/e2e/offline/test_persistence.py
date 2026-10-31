"""Harness self-tests for the persistence helpers: in-memory guild, real repositories, local database.

Needs DATABASE_URL (scripts/e2e.sh provides the throwaway one); skipped without it.
"""

from __future__ import annotations

import os
from datetime import timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio

from classes import Guild, clock
from classes.base.guildbase import GuildBase
from e2e.harness.core import E2E, guild_snapshot
from e2e.harness.env import E2EConfigError, check_throwaway_db
from e2e.offline import fakeguild
from store import dispose_engine, guild_repo, init_engine, load_state
from store.models import GalatronAttemptRow

pytestmark = pytest.mark.offline


@pytest_asyncio.fixture
async def db(fake):
    url = os.environ.get("DATABASE_URL", "")
    try:
        check_throwaway_db(url)
    except E2EConfigError:
        pytest.skip("DATABASE_URL (the throwaway database of scripts/e2e.sh) not set")
    init_engine(url)
    harness = E2E.__new__(E2E)
    harness.guild = fake.guild
    harness.bot = fake.bot
    harness._undo = []
    await harness._wipe_database()
    await guild_repo.ensure_guilds([(fake.guild.id, fake.guild.name)])
    state = await load_state()
    guild = Guild.from_state(fake.guild, state.guilds.get(fake.guild.id))
    try:
        yield SimpleNamespace(e2e=harness, guild=guild, fake=fake)
    finally:
        await harness._wipe_database()
        GuildBase._instances.pop(fake.guild.id, None)
        clock.reset()
        await dispose_engine()


async def test_write_through_holds_after_domain_mutations(db):
    guild, fake = db.guild, db.fake
    await guild.set_galatron_role(fake.guild.get_role(fakeguild.ADMIN_ROLE_ID))
    await guild.add_galatron_channel(fake.general)
    await guild.set_galatron_chance(0.25)
    await guild.galatron_record_attempt(fake.player, won=True)
    await guild.galatron_record_attempt(fake.admin, won=False)

    await db.e2e.assert_write_through()
    rebuilt = await db.e2e.assert_persisted(lambda g: g.galatron_log.get_current_owner().id == fake.player.id)
    assert guild_snapshot(rebuilt)["galatron_chances"][-1][1] == 0.25
    assert len(await db.e2e.rows(GalatronAttemptRow, guild_id=fake.guild.id)) == 2


async def test_write_through_catches_a_mutation_that_only_happened_in_memory(db):
    db.guild.galatron_channels.append(db.fake.general)

    with pytest.raises(AssertionError, match="memory and database disagree"):
        await db.e2e.assert_write_through()
    with pytest.raises(AssertionError, match="not persisted"):
        await db.e2e.assert_persisted(lambda g: g.galatron_channels != [])


async def test_rebuilding_does_not_disturb_the_live_registry(db):
    live = Guild.get(db.fake.guild.id)
    rebuilt = await db.e2e.rebuilt_guild()

    assert rebuilt is not live
    assert Guild.get(db.fake.guild.id) is live


async def test_attempts_are_stamped_with_the_test_clock(db):
    clock.advance(timedelta(days=2))
    await db.guild.galatron_record_attempt(db.fake.player, won=False)

    attempt = db.guild.galatron_log.attempts[0]
    assert timedelta(days=1, hours=23) < attempt.occurred_at - clock.now() + timedelta(days=2) < timedelta(days=2, minutes=1)
    await db.e2e.assert_write_through()


async def test_wiping_removes_the_guild_and_everything_below_it(db):
    await db.guild.galatron_record_attempt(db.fake.player, won=True)
    assert await db.e2e.rows(GalatronAttemptRow, guild_id=db.fake.guild.id)

    await db.e2e._wipe_database()

    assert await db.e2e.rows(GalatronAttemptRow, guild_id=db.fake.guild.id) == []
