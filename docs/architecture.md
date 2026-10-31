# Architecture

Paths in this document are relative to `backend/` unless they start with `backend/` or name a root file.

## Bootstrap flow

1. `main.py` calls `load_dotenv()` then `setup_logging()` (`logging_setup.py`), instantiates `ServiceDroid`, adds *only* `StartupCog`, then calls `bot.run()`.
2. `StartupCog.__init__` schedules `startup()` as a task. `startup()` waits for `wait_until_ready`, then:
   - Opens the DB: `init_engine(settings.database_url)`, then `guild_repo.ensure_guilds(...)` (one row per current guild, so the FK parent exists before any write).
   - `state = await load_state()` and reconstructs `Guild` objects via `Guild.from_state(guild, state.guilds.get(guild.id))`.
   - Builds trivia handlers via `TriviaHandler.load_from_state(bot, state["trivia"])`.
   - Instantiates all other cogs directly via `bot.add_cog(...)` (including `LoggingCog`). `TriviaCog._initial_schedule` then loads pending reveals via `trivia_repo.load_pending()`.
   - Calls `bot.sync_commands()` exactly once.

Cogs are **never** loaded via `bot.load_extension()`. Do not add `def setup(bot)` functions to cogs — they would be dead code and were removed deliberately. To add a new cog, add a `bot.add_cog(YourCog(self.bot))` line to `cogs/startup.py:startup()`.

Slash commands sync only at startup. After adding/removing/renaming a slash command, the bot must be restarted for Discord to see the change.

`StartupCog` sets `bot.startup_complete` (an `asyncio.Event`) as its very last step; the e2e harness (`docs/testing.md`) waits for it.

## Domain model

- `classes/base/guildbase.py:GuildBase` holds a class-level `_instances: dict[int, Guild]` registry.
- `classes/guild.py:Guild` extends it and aggregates LFG, Galatron, and Trivia state per Discord guild.
- `Guild.get(guild_id)` is the canonical lookup, used throughout the codebase. The registry is class-level, not bot-instance-level.
- `Guild.from_state(guild, None)` builds a fresh guild with defaults (no rows yet); the per-field defaults live in that `gs is None` branch.

## Context augmentation

`classes/context.py` defines `Context` and `ApplicationContext` subclasses that add convenience properties:
- `ctx.g` → the `Guild` object for the current guild
- `ctx.lfg` → `LFGData` helper (lazy properties for LFG channel/role checks)
- `ctx.galatron` → `GalatronData` helper (ApplicationContext only)

## Trivia scheduling

`classes/trivia_scheduler.py:TriviaScheduler` runs one asyncio task per trivia-bound channel that sleeps until the next cron tick (via `croniter`), posts a question, then schedules a separate one-shot task to reveal the answer after `config.response` seconds.

Currently only `MODE_TIMED` is implemented and only `ORDER_RANDOM` / `ORDER_SEQUENTIAL` are wired up. `MODE_AI` / `MODE_AI_TIMED` constants exist as placeholders and fall back to timed.

## Minecraft status channels

`classes/minecraft.py:MinecraftStatusUpdater` runs one asyncio task per mapped voice channel
(`MinecraftCog` mirrors `TriviaCog`: creates the updater, stores it on `bot.minecraft_updater`,
schedules all channels after `wait_until_ready`; `classes/reload.py` resyncs it on live reloads).
Each loop pings the server via **mcstatus** (`JavaServer.async_lookup` — direct Server List Ping,
resolves SRV records) and renames the channel only when the computed name differs.
`UPDATE_INTERVAL` (330 s) exists because Discord rate-limits channel renames to 2 per 10 minutes
per channel — don't lower it without accounting for that. The Restarting→Offline transition is
runtime-only state on `MinecraftStatusConfig` (`was_online`/`fail_count`, `OFFLINE_AFTER_FAILS`);
only `channel_id` + `address` are persisted (`minecraft_status_channel` table).

## Custom status emojis (for messages/embeds)

The owner's guild provides these custom emojis for status displays. They render **only in
messages/embeds — never in channel names** (channel names support Unicode emoji only, custom-emoji
markup shows as raw text there):

- `<:online:790788893943005204>` — green
- `<:idle:790788907980685352>` — orange
- `<:dnd:790788919574528040>` — red
- `<:offline:790788932098326549>` — grey
- `<:processing:790788943553364008>` — blue

## Guild-only gating (no DMs)

`classes/bot.py:ServiceDroid` drops everything that arrives without a guild, so the bot never acts in private/DM channels:

- `on_message` returns early when `message.guild is None`, so it never calls `process_commands` — **prefix commands** (e.g. `!lfg`) never run in DMs.
- `process_application_commands` returns early when `interaction.guild_id is None` — **slash commands** never run in DMs.

**Implication for command/context code:** by the time any command handler runs, a guild is guaranteed. `ctx.guild`, `ctx.guild_id`, and `ctx.g` / `Guild.get(ctx.guild.id)` are always valid — you do **not** need to null-check the guild or guard against DMs inside command bodies.

**The exception — raw event listeners.** This gating lives in the two methods above only. It does **not** cover `@commands.Cog.listener()` listeners (e.g. `EventsCog.on_message`, reaction handlers): py-cord dispatches those through the event system independently, so they still fire for DMs where `message.guild is None`. Any such listener must guard `if message.guild is None: return` itself before touching `message.guild` or `Guild.get(...)`.

## Sentinel pattern: `LFGNotAllowed`

`classes/lfg.py:LFGNotAllowed` is a class instantiated as a sentinel return value (`return LFGNotAllowed()`). Checks use `isinstance(x, LFGNotAllowed)`. Don't mix patterns — don't return the class itself or compare with `is`.

## Logging

- **Central setup:** `logging_setup.py:setup_logging()` is called once at the top of `main.py`. It sends
  records to **stdout** (the primary sink — captured and rotated by the Docker json-file log driver) **and**
  to a `RotatingFileHandler` at `<DATA_DIR>/logs/latest.log`. Level is `DEBUG` when `DEBUG` is truthy, else
  `INFO`; the `discord` logger stays at `INFO` to tame py-cord's gateway chatter unless `DISCORD_DEBUG` is
  truthy (then it drops to `DEBUG` — full gateway payloads, for troubleshooting only).
- **Never use `print()`** — every module logs via `logging.getLogger(__name__)`. The formatter already adds
  a timestamp, so don't prefix messages with one.
- **Command/event logging** lives in `cogs/logging_cog.py:LoggingCog` (registered in `startup()`): global
  listeners log every completed slash/prefix command (who, where, which command, options) and every error
  with traceback, under the `service_droid.commands` logger. This is the single place that makes "what was
  triggered, when, by whom" reconstructable from the log.
- **The in-Discord `/log` view** (`classes/log_view.py`, dev-only) tails the `RotatingFileHandler` file —
  `cogs/dev.py:LOG_PATH` is derived from `logging_setup.log_file_path()` so it always matches what the handler
  writes (honouring `DATA_DIR`). That file handler exists *for* this feature; stdout stays authoritative.

## Testing

The end-to-end suite in `backend/e2e/` drives the real bot with synthetic interactions; see [testing.md](testing.md). Domain code reads time through `classes/clock.py` so tests can advance it.

## Python / environment

- **DB stack:** `sqlalchemy[asyncio]>=2.0`, `psycopg[binary]>=3.2`, `alembic>=1.14` (`greenlet` comes in as a
  SQLAlchemy-async dependency). The driver is **psycopg 3 in async mode** (`postgresql+psycopg://`), **not
  asyncpg** — deliberate: psycopg ships cp314 wheels and matches the sibling grocery app's dependency, while
  giving the same non-blocking async behaviour. Don't swap in asyncpg without checking cp314 wheel availability.
- `from __future__ import annotations` (used in several `classes/*.py`) is technically redundant on 3.14
  (PEP 649 makes annotation evaluation lazy by default) but is kept for explicitness/back-compat — leave it.
