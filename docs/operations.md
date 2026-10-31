# Operations: running, deploying, configuring

Paths in this document are relative to `backend/` unless they start with `backend/` or name a root file.

## Running the bot

> **Live (2026-07-06):** both environments run on **ep3o** — prod from `main` at `/opt/service_droid`,
> dev from `dev` at `/opt/service_droid_dev` (separate bot token, `DEBUG=true`). The old `darquaise`
> host is **retired for service_droid** (only ChatCollector still runs there). **The PostgreSQL
> migration is fully done on both environments** (async SQLAlchemy 2.0 + psycopg 3, `store/`
> repositories, Alembic, write-through); the one-time JSON import is complete and the migration
> script has been removed. Snapshots of the old JSON data live locally in `backup/` (gitignored,
> split `prod/`/`dev/`). Remaining post-cutover tasks are tracked in the (untracked) `MIGRATION.md`.

### Server/infra facts (ep3o)

- `ssh root@ep3o` works directly (key auth). Prod deploy dir `/opt/service_droid`, dev `/opt/service_droid_dev`.
- Shared Postgres runs as Docker container **`shared-postgres`**; superuser access via
  `docker exec -i shared-postgres psql -U postgres -d <db>`. DBs/roles: prod `service_droid`/`service_droid_app`,
  dev `service_droid_dev` (same role naming scheme).
- Infra env: `/opt/main-server-infra/.env` holds `SERVICE_DROID_DB_PASSWORD` (prod) and
  `SERVICE_DROID_DEV_DB_PASSWORD` (dev); DBs are created with
  `/opt/main-server-infra/postgres/ensure-db.sh <db> <role> <pw>`.
- **Gotcha:** `docker exec -i … psql` swallows stdin when the outer script is fed via `ssh … 'bash -s'`
  heredoc — append `</dev/null` to every `docker exec -i`.
- Docker volume data on the host: `/var/lib/docker/volumes/<name>/_data`
  (volumes: `service-droid_sd-data`, `service_droid_dev_sd-data`; they hold only `logs/`).
- The `gh` CLI is **not** installed on the local Mac — check deploys via ssh to ep3o instead.

The bot runs as a **Docker container** — the container *is* the process; there is no `start.sh`/`screen`
anymore. Lifecycle is Docker's:

- **Prod/dev (ep3o):** `docker compose up -d --build` in the deploy dir (`/opt/service_droid` for prod,
  `/opt/service_droid_dev` for dev). GitHub Actions does this automatically on push to `main`/`dev`
  (see `.github/workflows/deploy.yml`).
- **Restart policy:** `restart: unless-stopped` — Docker restarts the container on *any* exit (crash or
  `/restart`). The old "exit 42 = restart, anything else = stop" loop is gone; `/restart` still works
  because the container simply exits (still with code 42) and Docker brings it back.
- **Logs:** `docker compose logs -f bot`. Rotation is handled by the json-file log driver (`compose.yml`),
  not the shell.
- **Local dev:** `./scripts/dev-start.sh` (mirrors grocery's `scripts/dev-*.sh`) brings up a throwaway
  local Postgres (`compose.dev.yml`, loopback **:5433**), applies migrations (`alembic upgrade head`),
  and runs the bot in the background (`.dev/bot.log`). The DB starts **empty** (no seeding — configure
  via Discord commands or psql). Companions:
  `dev-stop.sh`, `dev-restart.sh`, `dev-reset.sh` (reset wipes the local DB volume). The scripts
  pass `DATABASE_URL` to the bot as a **real env var**, which `load_dotenv` won't override — so local runs
  **never** touch the server DB regardless of what `.env` contains. Requires Docker (e.g. `colima start`).
  To run by hand instead: set `DATABASE_URL` yourself, ensure the schema (`alembic upgrade head`), then
  `cd backend && uv run python main.py`.

`COMPOSE_PROJECT_NAME` (in `.env`) selects the environment: `service-droid` (prod) vs `service_droid_dev`
(dev). The dev env uses a **separate Discord application/token** and `DEBUG=true`.

## Configuration

All config lives in `.env` (gitignored). Template is `.env.example`:

- `DEBUG` — bool; when true, **all** slash commands are scoped to `DEBUG_GUILD_IDS` (main.py), and the root log level is `DEBUG`
- `DISCORD_DEBUG` — bool, default false; when true the `discord` (py-cord) loggers emit at `DEBUG` (full gateway payloads — very verbose, troubleshooting only). **Independent of `DEBUG`**: read directly from env in `logging_setup.setup_logging()` (not via `Settings`), so it applies even before `Settings` is built. `DEBUG` alone leaves `discord` pinned at `INFO`.
- `DEBUG_GUILD_IDS` — comma-separated guild IDs; also the always-on scope for `cogs/dev.py` slash commands
- `COMPOSE_PROJECT_NAME` — compose project / environment name: `service-droid` (prod) vs `service_droid_dev` (dev)
- `DATABASE_URL` — PostgreSQL DSN, **async psycopg 3 driver**: `postgresql+psycopg://user:pw@host:5432/db`. In the container the host is the shared-db service name `postgres`; locally point it at your own Postgres. Consumed by `Settings` (the app) *and* `migrations/env.py` (Alembic). **Required** — `Settings.__init__` reads `os.environ["DATABASE_URL"]` and will KeyError if unset.
- `DATA_DIR` — base dir for the **log file only** now (`<DATA_DIR>/logs/latest.log` for the `/log` view). Container: `/app/data` (the `sd-data` volume); locally defaults to `.`. (No longer holds bot data — that lives in Postgres.)

`classes/settings.py:env_int_list(name)` is the helper for parsing comma-separated int lists from env. Use it for any new ID-list vars.
`Settings` consumes env at construction; `cogs/dev.py` reads `DEBUG_GUILD_IDS` at **module-import time** because slash-command decorators need the value at class-definition time. `main.py` calls `load_dotenv()` **before** importing `Settings` or any cog, so the env is fully populated by the time these run (in Docker the real env vars from compose take precedence; `load_dotenv` does not override them).
