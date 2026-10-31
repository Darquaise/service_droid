# Testing (end-to-end harness)

Paths in this document are relative to `backend/` unless they start with `backend/` or name a root file.

The suite in `e2e/` starts the **real bot** (same bootstrap as `main.py`, same cogs, same database layer) against a
non-production test bot and a test guild, and drives it with **synthetic interactions**. The Discord side is real,
except for the answers to interactions (see below). Inside the bot only these are replaced, and only where a test asks:
`random` in `cogs/galatron_commands` (`force_*`), the Minecraft server query (`mock_minecraft`) and the clock offset;
DMs are swallowed for every test (see *Owner DMs*).

## How it works

- **Synthetic interactions** (`e2e/harness/pycord.py`): a slash command or a button/select click is turned into a raw
  `INTERACTION_CREATE` payload and fed to `bot._connection.parse_interaction_create(...)`. Command resolution,
  option conversion, checks, the callback and the error handlers therefore run exactly as for a real user. The
  invoking member is the real cached `Member` of a dummy.
- **Intercepted routes.** py-cord answers an interaction through `AsyncWebhookAdapter.request`
  (`webhook/async_.py`), **not** through `HTTPClient`: the first response (`/interactions/{id}/{token}/callback`),
  followups (`/webhooks/{app}/{token}`) and `@original`/message edit/get/delete. Exactly those requests whose
  token starts with `e2e.` (our synthetic ones) are caught and recorded instead of being sent — Discord would
  reject them, the interaction does not exist there. What Discord would refuse is refused here too: a first answer
  later than 3 s after the interaction raises `NotFound` (10062 Unknown interaction), and a body over Discord's limits
  (content 2000, 10 embeds / 6000 characters, field/title/footer lengths, 5 action rows of 5 items, labels, custom_ids,
  25 select options) raises `HTTPException` (50035 Invalid Form Body) — inside the bot, as in production. Every other request goes to real Discord untouched: `channel.send`,
  role changes, channel edits, history reads.
- **Captured responses** are `Response` objects (`e2e/harness/pycord.py`): `.original`, `.followups`, `.text`,
  and per message `.content`, `.embeds`, `.files` (name + bytes), `.ephemeral`, `.components`, `.edits`, `.deleted`. A
  message edited later (edit_original_response, a select/button callback) is updated in place.
- **Mirroring**: each captured message is also posted as a real message into the channel the command ran in (into
  the sandbox `log` channel when the bot cannot write there), with a `-# e2e · /command · user` header. This is only
  for a human looking at the guild after a run; tests assert on the captured data. Mirrors go through a background
  queue (a real `channel.send` with its rate limits must not delay the bot's answer) that is flushed before each test.
- **Completion**: `slash()`/`click()` return once the command (or the view callback) finished; when it raised, also
  once py-cord's error handler tasks (`on_application_command_error`, `on_view_error`) finished, so their answer is part
  of the `Response`. A callback that raises fails the test with `CommandFailed` unless `expect_error=True`. A click on a
  stopped view fails at once with `HarnessError`.
- **Discord-side gating is emulated**: py-cord never checks `default_member_permissions` (Discord does), so
  `slash()` raises `CommandNotAvailable` when the invoking member lacks them (`enforce_permissions=False` skips it).
- **Bot permissions**: the test bot is an Administrator in Discord, which makes py-cord skip channel overwrites. The
  harness strips Administrator from the bot's *cached* roles (`demote_bot_admin`), so the sandbox channels that are
  broken for the bot on purpose (`galatron_no_attach`, `galatron_no_send`, `trivia_no_embed`, `voice_no_manage`) really
  fail the bot's own checks. A `GUILD_ROLE_UPDATE` of one of the bot's roles refreshes the cache, so the session
  fixture demotes again on every such event. Discord itself still lets the bot do everything, so a real `Forbidden` can't be produced.
- **Clock**: bot code never calls `datetime.now()`; it uses `classes/clock.py`. `e2e.advance_time(td)` shifts it.
  Real `asyncio.sleep` and gateway timing are unaffected, so scheduler loops are driven by calling the scheduler's own
  tick (`TriviaScheduler._fire`, `_deliver_pending`) rather than by waiting for the cron time; the cron loop itself is
  run with a fake `asyncio.sleep` that advances the clock (`test_the_loop_sleeps_until_the_next_cron_tick_of_the_clock`).
- **Owner DMs**: `Member.send`/`User.send` are replaced for the whole session — tests never DM a real person.
  `notify_owner` runs for real (deduplication included); what it would DM the owner lands in `e2e.notices`.
- **Minecraft**: `e2e.mock_minecraft(online=3)` replaces `JavaServer.async_lookup`; `None` means unreachable.

Every py-cord internal the harness relies on lives in `e2e/harness/pycord.py`. Patching an attribute that does not exist
(renamed in a py-cord upgrade) raises a `HarnessError` naming the py-cord version instead of silently timing out.

### Test isolation

The session starts the bot once. Before each test, `e2e` resets the guild: its database rows are deleted and the
registry is rebuilt (`reload_guild`), the clock offset, LFG cooldowns, patches and the roles the dummies hold are
cleared. A test sets up its own state through commands and ends with persistence checks:

- `await e2e.assert_persisted(lambda g: ...)` rebuilds a `Guild` from `load_state()` (without disturbing the live
  registry) and asserts the predicate on it — proof that the change was written through, not only held in memory.
- `await e2e.assert_write_through()` compares all persisted fields of the live guild with the rebuilt one (and the
  trivia lists).
- `await e2e.rows(SomeRow, guild_id=...)` reads rows of any `store.models` table.

### Per-run sandbox

Each run creates a category `e2e-<run>` with its channels and roles in the test guild and deletes them afterwards,
also when tests fail. Leftovers (`e2e-*` categories, channels and roles) of a crashed run are removed at the next
start, once they are older than 30 minutes (`STALE_AFTER`) — a younger one may belong to a run on another machine. The first dummy gets an Administrator role per run and is `e2e.admin`; `e2e.member` is the second dummy.

## One-time setup

1. **Test bot.** Any non-production bot works; the local dev bot from `.env` (Betabot) is the default. It needs
   all three privileged intents (Presence, Server Members, Message Content): the bot uses `Intents.all()`.
   **Never a production bot** (Service Droid, Vibebot): the run syncs the test command set over that bot's slash
   commands. `harness/env.py` refuses their tokens (`FORBIDDEN_BOT_IDS`, read from the token's first segment).
   The same token must not be logged in elsewhere during a run — `scripts/e2e.sh` aborts while the local dev bot
   (`scripts/dev-start.sh`) of this checkout is running.
2. **Test guild.** A server where channels and roles may be created freely (default: `576380164250927124`). The test
   bot needs **Administrator** there. Being in other servers is fine: with the empty throwaway DB nothing is
   configured there, and only the test guild's commands are synced.
3. **Dummies.** 2–3 other bots that are members of the test guild (default: Astromech, NOOBICON). They are never
   driven: their member objects are only the authors of synthetic interactions and may receive test roles.
   Three are recommended; tests that need a third player use the admin dummy, so two is the minimum.
   The **second** dummy is the plain member and must not be an administrator through its own roles (the harness
   aborts otherwise); a bot that already is one belongs in the first slot.
4. **Role order.** In the test guild, make sure the test bot's role is above the roles the harness creates
   (new roles are created at the bottom, so the default is fine). Do not move the dummies' roles above it.
5. `cp .env.e2e.example .env.e2e` and fill `DISCORD_TOKEN`, `E2E_GUILD_ID`, `E2E_DUMMY_USER_IDS`
   (comma-separated). `DATABASE_URL` is provided by the script. The file is gitignored. The repo's `.env` is never read.

## Running

```
./scripts/e2e.sh                 # everything
./scripts/e2e.sh -k galatron     # a subset (arguments go to pytest)
./scripts/e2e.sh -m offline      # only the harness self-tests, incl. the ones that need the database
```

The script starts a throwaway Postgres (`compose.e2e.yml`, compose project `service-droid-e2e`, tmpfs, port 5434 or
`$E2E_DB_PORT`), runs `alembic upgrade head`, runs `uv run pytest e2e` and removes the database again. It needs
Docker (e.g. `colima start`), fails fast when Docker or `.env.e2e` is missing, and holds the machine-wide lock
`~/.cache/service_droid/e2e.lock` so only one run (from any checkout) uses the token at a time. The local dev database (`compose.dev.yml`) is not touched. The `-p` on the compose
calls matters: `.env` sets `COMPOSE_PROJECT_NAME`, which would otherwise point the e2e database at the dev project.

Live tests run **only through the script**: `harness/env.py` refuses unless `E2E_RUNNER_PID` (set by the script)
matches the pid in the lock and that process is alive, and unless `DATABASE_URL` is the throwaway database
`localhost/service_droid_e2e` — the tests delete guild data, so the local dev database (`localhost:5433/service_droid`)
is refused too. `uv run pytest e2e` without the script collects fine and **skips** the live tests with that message
(`E2E_REQUIRED=1`, set by the script, turns a skip into a failure).

The tests under `e2e/offline/` need no Discord: they check the harness itself (payloads accepted by py-cord, response
capture, view clicks, clock, persistence helpers) and run on every `./scripts/e2e.sh`. The persistence self-tests also
need the throwaway database and skip without it, so `uv run pytest e2e -m offline` alone runs the rest.

## Git hooks

Activate once per clone:

```
git config core.hooksPath .githooks
```

- `.githooks/pre-commit` (seconds) — when the commit touches `backend/` (or the e2e scripts/compose file/hooks):
  `ruff check`, the clock rule (no `datetime.now(`/`utcnow(` in `classes/`, `cogs/`, `converters/`, `store/` outside
  `classes/clock.py`) and `pytest e2e -m offline`. It checks the working tree, not what is staged.
- `.githooks/pre-push` (~4 min) — when the pushed commits touch `backend/` or the e2e files: `scripts/e2e.sh`, the full
  live suite. It aborts with a message when `.env.e2e` or Docker is missing, or while the local dev bot runs.

Skip once with `git commit --no-verify` / `git push --no-verify`.

## Writing a test

```python
from datetime import timedelta
from e2e.tests.helpers import attempt, fail, register, setup_galatron, win

async def test_cooldown(e2e):
    await setup_galatron(e2e)                      # real settings commands
    player = e2e.players[0]
    await fail(e2e, player)                        # force_fail() + /attempt_galatron

    rejected = await attempt(e2e, player)
    assert rejected.original.ephemeral

    e2e.advance_time(e2e.g.galatron_cooldown + timedelta(seconds=1))
    assert not (await fail(e2e, player)).original.ephemeral
    await e2e.assert_write_through()
```

- `e2e.slash("command", "subcommand", user=member, in_channel=channel, option=value, ...)` — `user` defaults to
  `e2e.admin` for admin-only commands, else `e2e.member`; `in_channel` defaults to `sandbox.general` (not called
  `channel` because many commands have an option of that name). Option values are Python objects (`Member`, `Role`,
  channels, `int`, `float`, `str`); wrong names, missing required options and invalid choices fail loudly.
- `e2e.click(response, "label-or-custom_id")`, `e2e.select(response, "placeholder-or-custom_id", "value")`. The click
  comes from whoever ran the command unless `user=` says otherwise. py-cord generates random `custom_id`s, so use the label.
- Channels and roles: `e2e.sandbox.galatron`, `.galatron_no_attach`, `.lfg`, `.trivia`, `.voice`, `.galatron_role`, …
  (`e2e/harness/sandbox.py`). A permission lost *after* setup is simulated by adding the broken channel through the
  domain method (`await e2e.g.add_galatron_channel(...)`), since the setup command correctly refuses it.
- Randomness: `e2e.force_win()`, `force_fail()`, `force_random(...)`, `force_all_contexts()`; asserting on message text
  is done against the pools in `galatron_text` (`pool_matches(pool, text)`), so no seeding is needed.
- Real messages the bot posted: `await e2e.history(channel)` — newest first, only from the current test, mirrors
  excluded. Owner notices: `e2e.notices`.
- `e2e.patch(owner, "name", value)` replaces an attribute until the next test.
- Listeners: `await e2e.member_remove(member)` calls `EventsCog.on_member_remove` with a real dummy `Member` — the
  dummies are never actually kicked, they can't be re-invited automatically.
- Mind the second: attempts are stored with `microsecond=0`, so after changing a setting `advance_time(2s)` before
  an attempt that should fall under the new value.

## The clock rule

Bot code never calls `datetime.now()` / `datetime.now(timezone.utc)` for domain logic — use `classes/clock.py`
(`clock.now()` naive local time, `clock.now_utc()` aware UTC). Otherwise tests can't move time. `time.monotonic()`
(owner-notice dedup in `classes/permissions.py`) and `asyncio.sleep` are not domain time and stay as they are.

## Not covered

- Real permission failures from Discord (`Forbidden` on role assignment, a role above the bot's role): the bot is an
  administrator there; only its local permission checks can be made to fail.
- The 330 s Minecraft update loop: its tick is invoked directly, the waiting is real-time.
- Autocomplete, modals, prefix commands (`!lfg`) and gateway events other than the ones a test dispatches itself.
