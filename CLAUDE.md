# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Docs split: who reads what

- **`README.md` is for *users* of the bot** — server admins configuring it and operators self-hosting it. It covers setup, the `.env` values, and the user-facing command reference. It is **not** a development guide and should not be relied on for continuing development.
- **`CLAUDE.md` (this file) is the development reference** — architecture, invariants, internal mechanisms, and the gotchas you need before changing code.
- When you find development-only detail (internal method names, design rationale, schema/lifecycle invariants) leaking into `README.md`, move it here instead of duplicating it there.

## Running the bot

- `./start.sh` is the intended entry point. It spawns `.start.sh` in a detached `screen` session named `service_droid`.
- `.start.sh` sources `.env`, activates `.venv`, installs `requirements.txt`, and runs `main.py` in a restart loop.
- Exit code **42** signals "restart" (used by `/restart` dev command). Any other exit code stops the loop.
- Logs rotate on each restart: `logs/latest.log` is the live file, rotated files use `<start_ts>__<end_ts>.log` in `logs/`.
- Reattach to the running bot: `screen -r service_droid`.

`python main.py` directly does **not** load `.env` — env loading happens in `.start.sh`.

## Configuration

All config lives in `.env` (gitignored). Template is `.env.example`:

- `DISCORD_TOKEN` — bot token (secret)
- `DEBUG` — bool; when true, **all** slash commands are scoped to `DEBUG_GUILD_IDS` (main.py)
- `COMMAND_PREFIX` — for legacy prefix commands (currently only `!lfg`)
- `OWNER_IDS` — comma-separated user IDs
- `DEBUG_GUILD_IDS` — comma-separated guild IDs; also the always-on scope for `cogs/dev.py` slash commands

`classes/settings.py:env_int_list(name)` is the helper for parsing comma-separated int lists from env. Use it for any new ID-list vars.
`Settings` consumes env at construction; `cogs/dev.py` reads `DEBUG_GUILD_IDS` at **module-import time** because slash-command decorators need the value at class-definition time (cogs are imported lazily by `StartupCog`, which runs after `.env` has been sourced).

## Persistence

- `guilds.json` — per-guild config (LFG channels/roles, Galatron state, Trivia mappings). Rewritten in full by `Settings.update_guilds()` after every mutation.
- `trivia/<guild_id>.json` — per-guild Trivia question lists. Rewritten by `Settings.update_trivia(guild_id)`.
- `trivia/_pending.json` — see "Trivia answer persistence" below.
- The paths `"guilds.json"` and `"trivia"` are **hardcoded** in `Settings.__init__`, not env-configurable. The pending path is derived as `trivia/_pending.json`.

### Atomic writes

`ios/json.py:write_json` writes to a temp file in the same directory, `fsync`s it, then `os.replace`s it over the target. A crash/kill mid-write therefore can never leave a truncated or corrupt JSON file — the previous contents survive until the rename completes. **All** persistence goes through this function, so don't reintroduce a plain `open(path, "w")` + `json.dump` anywhere.

### Trivia answer persistence

Goal: a restart between a question being posted and its answer being revealed must not silently swallow the answer.

- Each `TriviaChannelConfig` carries a transient `pending` dict (`{due_at, title, answer, answer_context}`), set via `set_pending()` when a timed question fires and cleared via `clear_pending()` once the answer is revealed.
- `Settings.update_trivia_pending()` rebuilds `trivia/_pending.json` from the live `pending` of **all** trivia channels on every set/clear. Because it rebuilds from scratch, entries for channels that no longer exist are dropped automatically (no orphan cleanup needed).
- On startup, `cogs/trivia.py:_initial_schedule` loads the file and assigns each entry to the matching channel's `cfg.pending` before scheduling. `TriviaScheduler._loop_for_channel` then calls `_deliver_pending` **first**, before entering the cron loop.
- **`_deliver_pending` only re-delivers answers whose reveal time is still in the future** (`due_at` not yet reached): it sleeps the remainder, posts, and clears. If the reveal time has already passed (`remaining <= 0`) the answer is discarded. This is intentional — for short response windows a restart usually outlasts the window, so most restarts will discard rather than re-deliver. (To change this, add a grace period in `_deliver_pending`.)
- **Validation lives in one place:** `Settings.load_trivia_pending` is the single load point and validates structurally (`due_at` numeric, `title`/`answer` strings), wraps the read in try/except, and drops malformed entries. Downstream code (`_initial_schedule`, `_deliver_pending`) therefore trusts the shape and accesses keys directly — don't re-add defensive checks there; harden `load_trivia_pending` instead.

## Architecture

### Bootstrap flow

1. `main.py` instantiates `ServiceDroid` and adds *only* `StartupCog`, then calls `bot.run()`.
2. `StartupCog.__init__` schedules `startup()` as a task. `startup()` waits for `wait_until_ready`, then:
   - Loads `guilds.json` and reconstructs `Guild` objects.
   - Loads per-guild trivia JSON files via `TriviaHandler.load_all`.
   - Instantiates all other cogs directly via `bot.add_cog(...)`.
   - Calls `bot.sync_commands()` exactly once.

Cogs are **never** loaded via `bot.load_extension()`. Do not add `def setup(bot)` functions to cogs — they would be dead code and were removed deliberately. To add a new cog, add a `bot.add_cog(YourCog(self.bot))` line to `cogs/startup.py:startup()`.

Slash commands sync only at startup. After adding/removing/renaming a slash command, the bot must be restarted for Discord to see the change.

### Domain model

- `classes/base/guildbase.py:GuildBase` holds a class-level `_instances: dict[int, Guild]` registry.
- `classes/guild.py:Guild` extends it and aggregates LFG, Galatron, and Trivia state per Discord guild.
- `Guild.get(guild_id)` is the canonical lookup, used throughout the codebase. The registry is class-level, not bot-instance-level.
- `Guild.from_nothing(guild)` delegates to `from_json(guild, {})`; defaults live exclusively in `from_json`'s else-branches — don't duplicate them.

### Context augmentation

`classes/context.py` defines `Context` and `ApplicationContext` subclasses that add convenience properties:
- `ctx.g` → the `Guild` object for the current guild
- `ctx.lfg` → `LFGData` helper (lazy properties for LFG channel/role checks)
- `ctx.galatron` → `GalatronData` helper (ApplicationContext only)

### Trivia scheduling

`classes/trivia_scheduler.py:TriviaScheduler` runs one asyncio task per trivia-bound channel that sleeps until the next cron tick (via `croniter`), posts a question, then schedules a separate one-shot task to reveal the answer after `config.response` seconds.

Currently only `MODE_TIMED` is implemented and only `ORDER_RANDOM` / `ORDER_SEQUENTIAL` are wired up. `MODE_AI` / `MODE_AI_TIMED` constants exist as placeholders and fall back to timed.

### Guild-only gating (no DMs)

`classes/bot.py:ServiceDroid` drops everything that arrives without a guild, so the bot never acts in private/DM channels:

- `on_message` returns early when `message.guild is None`, so it never calls `process_commands` — **prefix commands** (e.g. `!lfg`) never run in DMs.
- `process_application_commands` returns early when `interaction.guild_id is None` — **slash commands** never run in DMs.

**Implication for command/context code:** by the time any command handler runs, a guild is guaranteed. `ctx.guild`, `ctx.guild_id`, and `ctx.g` / `Guild.get(ctx.guild.id)` are always valid — you do **not** need to null-check the guild or guard against DMs inside command bodies.

**The exception — raw event listeners.** This gating lives in the two methods above only. It does **not** cover `@commands.Cog.listener()` listeners (e.g. `EventsCog.on_message`, reaction handlers): py-cord dispatches those through the event system independently, so they still fire for DMs where `message.guild is None`. Any such listener must guard `if message.guild is None: return` itself before touching `message.guild` or `Guild.get(...)`.

### Sentinel pattern: `LFGNotAllowed`

`classes/lfg.py:LFGNotAllowed` is a class instantiated as a sentinel return value (`return LFGNotAllowed()`). Checks use `isinstance(x, LFGNotAllowed)`. Don't mix patterns — don't return the class itself or compare with `is`.

## Python / environment

- Python 3.14.x. On this machine the interpreter used to build the venv is Homebrew's `python@3.14` (`/opt/homebrew/bin/python3.14`); a python.org 3.14 would work just as well.
- py-cord **2.8** (`requirements.txt` pins `>=2.8.0`). 2.8 added Python 3.14 support and lifted the old `<3.14` cap, so the project now runs on 3.14. Ships native cp314 wheels for `aiohttp`/`yarl`/etc.
- The codebase uses **no** APIs that 2.8 deprecated or removed. The only `discord.VoiceClient` reference is a type annotation in `classes/base/guildbase.py`, inert under `from __future__ import annotations`. The only `DeprecationWarning`s at runtime come from py-cord's own internals (`asyncio.iscoroutinefunction`, relevant only at Python 3.16) — nothing actionable here.
- `from __future__ import annotations` (used in several `classes/*.py`) is technically redundant on 3.14 (PEP 649 makes annotation evaluation lazy by default) but is kept for explicitness/back-compat — leave it.
- **venv fragility:** `.venv` is built against a specific interpreter. If that interpreter disappears (e.g. `brew upgrade` replaces/removes the Python it was built on), `.venv/bin/python` becomes a dangling symlink and *everything* breaks with "no such file or directory". Fix = `rm -rf .venv` and recreate with a 3.14 interpreter, then `./start.sh` reinstalls deps.
- Dependencies in `requirements.txt`. `requirements-dev.txt` is for ad-hoc scripts (currently only `test.py`).

## Things to verify before claiming work is done

- After editing a cog, restart the bot (`/restart` slash command or kill the `screen` session) — there is no hot reload.
- After changing the set/signature of slash commands, restart is required for them to appear/update in Discord.
- After changing the `guilds.json` schema, update both `Guild.from_json` (read) and `Guild.to_json` (write). Backward-compat for existing payloads is implicit via `.get(key, default)`.
- After mutating any `Guild` field, call `self.bot.settings.update_guilds()`. After mutating trivia data, call `self.bot.settings.update_trivia(guild_id)`.