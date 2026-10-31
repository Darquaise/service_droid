# Persistence

Paths in this document are relative to `backend/` unless they start with `backend/` or name a root file.

Data lives in **PostgreSQL**, accessed through **async SQLAlchemy 2.0 + psycopg 3** (async mode). The
former JSON files (`guilds.json`, `trivia/*.json`) and `ios/json.py` are **gone**. The whole DB layer
is the **`store/`** package — nothing else touches the database:

- **`store/models.py`** — SQLAlchemy 2.0 ORM models, one per table (normalized).
  Class names carry a **`Row` suffix** (`GuildRow`, `TriviaQuestionRow`, …) so they never clash with the
  in-memory domain classes in `classes/`.
- **`store/engine.py`** — `init_engine(database_url)` (called once in `cogs/startup.py`),
  `dispose_engine()` (called in `ServiceDroid.close()`), `session_factory()`.
- **`store/repositories.py`** — the singletons `guild_repo` / `lfg_repo` / `galatron_repo` / `trivia_repo`
  plus `load_state()`. Each mutating method is a small, self-contained transaction.
- **`store/state.py`** — plain dataclasses (`LoadedState`, `GuildState`, `QuestionData`, …) that
  `load_state()` fills from the rows and the domain builds its objects from. No JSON-shaped dicts.

**Schema is owned by Alembic** (`backend/alembic.ini`, async `backend/migrations/env.py`,
`migrations/versions/0001_initial.py`). The container runs `alembic upgrade head` before `python main.py`
(Dockerfile CMD). After any change to `store/models.py`, add a migration — `migrations/env.py` reads
`DATABASE_URL` and targets `store.models.Base.metadata`.

## Read once, write through (the core invariant)

- **Reads:** the in-memory domain registry (`Guild.get`, `TriviaHandler`, `ctx.g`) is built **once at
  startup** from `store.load_state()` — there is **no query per command**. `load_state()` groups the
  relational rows into the **typed structs in `store/state.py`** (`LoadedState` → `GuildState` /
  `QuestionData` / …) and the domain builds its objects directly from them via `Guild.from_state` /
  `TriviaHandler.load_from_state`. There is **no JSON-shaped intermediate**.
- **Writes:** every mutation is a **granular async write-through** on a domain method — it mutates memory
  **and** `await`s a repo that writes exactly the changed row(s). There is **no** "serialize everything
  after each change" step; `Settings.update_guilds/update_trivia/update_trivia_pending` are **gone**.
  Examples: `Guild.set_cooldown` → `lfg_repo.upsert_host_role`; `Guild.galatron_record_attempt` →
  `galatron_repo.add_attempt`; `TriviaHandler.add_question` → `trivia_repo.add_question`.
  **Cogs must not** re-introduce a "save" call after calling a domain method — the domain method persists.
- **No JSON (de)serialization layer:** the domain classes have **no `to_json()`/`from_json()`** — the
  relational tables are the only representation. The former JSON dev commands (`/export_guilds`,
  `/export_trivia`, `/inject_trivia`) were **removed**; nothing serialises the domain to/from JSON anymore.
- **Time fields** cross the repo boundary as **epoch seconds** (mirroring the old JSON) and are stored as
  `timestamptz`; they round-trip back to the same epoch the domain already used. Keep that convention.
- **Adding a mutation:** add an `async` domain method that mutates memory then `await`s a repo method;
  add the repo method (granular upsert/delete) in `store/repositories.py` — and call `emit_change(s, guild_id)`
  inside its transaction (see "Live reload" below); add the column/table + an Alembic migration if the schema changes.

## Live reload / external writes (the web UI will share this DB)

The registry is built once at startup, so a writer **outside this process** (the planned web UI on the same
database) would otherwise be invisible to a running bot — and a stale in-memory write could clobber its change.
The change-bus in `store/notify.py` addresses both:

- **Notify:** every guild-scoped repo write calls `emit_change(session, guild_id)` — a *transactional*
  `pg_notify` on the `sd_changes` channel carrying the guild id + this process's `ORIGIN`. Skipped only for
  pure runtime/channel-scoped writes (`set_channel_next_index`, `upsert_pending`/`delete_pending`).
- **Listen:** `cogs/startup.py:startup()` creates a `ChangeListener` (`store/notify.py`) on a **dedicated**
  psycopg connection (auto-reconnecting) with `reload_guild` as its callback, and stores it on
  `bot.change_listener`; on a notification it calls `classes/reload.py:reload_guild(bot, guild_id)`, **ignoring
  notifications whose `origin` matches its own `ORIGIN`** (the bot's own writes already updated memory). The
  listener is stopped from `ServiceDroid.close()` (via `bot.change_listener`). There is deliberately **no
  cog** for this — it's a bootstrap/lifecycle step, not command/event handling.
- **`classes/reload.py:reload_guild`** re-reads one guild via `store.load_guild_state`, rebuilds the `Guild` aggregate
  (`from_state`) and its `TriviaHandler` (`replace_for_guild`), then **resyncs the scheduler**: cancel
  vanished channels, reschedule the rest. In-flight answers survive because a cancel-*while-waiting* keeps the
  `trivia_pending` row (only a cancel mid-send clears it), so the rescheduled loop re-delivers. `/reload
  [guild_id]` (dev) triggers a reload manually; `NOTIFY sd_changes, '{"guild_id": <id>}'` from psql exercises
  the listener end-to-end.
- **No contended counters:** Galatron attempts are append-only inserts (one row per attempt), so concurrent
  writers can't lose a count — totals are a `COUNT`, never an incremented column. `next_index` stays in-memory
  (bot-owned, single writer).

## Trivia answer persistence

Goal: a restart between a question being posted and its answer being revealed must not silently swallow the answer.

- Each `TriviaChannelConfig` carries a transient `pending` dict (`{due_at, title, question, answer, answer_context}` — `question` is the exact wording that was posted), set via `set_pending()` when a timed question fires and cleared via `clear_pending()` once the answer is revealed.
- The DB mirror is the **`trivia_pending`** table: the scheduler `await`s `trivia_repo.upsert_pending(...)` on set and `trivia_repo.delete_pending(...)` on clear (granular, not a full rewrite). `Guild.remove_trivia_channel` also deletes the channel's pending row, so orphans can't accumulate.
- **Cancellation paths** (`except asyncio.CancelledError` in `_reveal_answer` / `_deliver_pending`) can't `await` — they call `TriviaScheduler._clear_pending_detached(channel_id)`, which fires the delete as a detached task on the still-running loop, then re-raise.
- On startup, `cogs/trivia.py:_initial_schedule` calls `await trivia_repo.load_pending()` and assigns each entry to the matching channel's `cfg.pending` before scheduling. `TriviaScheduler._loop_for_channel` then calls `_deliver_pending` **first**, before entering the cron loop.
- **`_deliver_pending` only re-delivers answers whose reveal time is still in the future** (`due_at` not yet reached): it sleeps the remainder, posts, and clears. If the reveal time has already passed (`remaining <= 0`) the answer is discarded. This is intentional — for short response windows a restart usually outlasts the window, so most restarts will discard rather than re-deliver. (To change this, add a grace period in `_deliver_pending`.)
- Pending rows are well-typed by the schema (`due_at timestamptz`, `title`/`answer text`), so `load_pending` needs no structural validation — `_initial_schedule` / `_deliver_pending` access keys directly.
