#!/usr/bin/env bash
#
# Starts the bot LOCALLY and offline:
#   - Postgres in Docker (compose.dev.yml) — no server DB needed
#   - schema via Alembic (same as production)
#   - bot (uv run python main.py), in the background with a PID file + log file
#
# Usage:   ./scripts/dev-start.sh
# Logs:    tail -f .dev/bot.log
# Stop:    ./scripts/dev-stop.sh
#
# Note: production is left untouched (compose.yml -> the real shared Postgres).
# The local DATABASE_URL is passed to the bot as a real env var and therefore
# takes precedence over anything in .env. So a local run NEVER hits the server DB.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.dev"
mkdir -p "$RUN_DIR"

DEV_DB_URL="postgresql+psycopg://service_droid_app:service_droid@localhost:5433/service_droid"

for tool in docker uv; do
  command -v "$tool" >/dev/null 2>&1 || { echo "✗ '$tool' not found."; exit 1; }
done
docker info >/dev/null 2>&1 || { echo "✗ Docker daemon is not running (e.g. 'colima start')."; exit 1; }

if [ ! -f "$ROOT/.env" ]; then
  echo "⚠ No .env found — without DISCORD_TOKEN the bot cannot log in."
  echo "  Tip: cp .env.example .env  and fill in DISCORD_TOKEN (DATABASE_URL is overridden locally)."
fi

# First-time dependency install only if missing (one-off, online).
[ -d "$ROOT/backend/.venv" ] || ( echo "▶ uv sync (one-off)…"; cd "$ROOT/backend" && uv sync )

# 1) Start the database and wait until it is "healthy".
echo "▶ Database (Docker)…"
docker compose -f compose.dev.yml up -d --wait

# 2) Schema via Alembic (same as production) — incremental migrations.
echo "▶ Database migrations (alembic upgrade head)…"
( cd "$ROOT/backend" && env DATABASE_URL="$DEV_DB_URL" uv run alembic upgrade head )

# Starts a background process with a PID file + log file (survives script exit).
start_bg() {  # name workdir command...
  local name="$1" dir="$2"; shift 2
  local pidfile="$RUN_DIR/$name.pid" logfile="$RUN_DIR/$name.log"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile" 2>/dev/null)" 2>/dev/null; then
    echo "  $name is already running (PID $(cat "$pidfile"))."
    return
  fi
  ( cd "$dir" && exec nohup "$@" ) >"$logfile" 2>&1 &
  echo $! >"$pidfile"
  disown %% 2>/dev/null || true
  echo "  $name → PID $!  ·  Log: ${logfile#"$ROOT"/}"
}

# 3) Bot — DATABASE_URL forces the local DB.
echo "▶ Bot (py-cord)…"
start_bg bot "$ROOT/backend" \
  env DATABASE_URL="$DEV_DB_URL" uv run python main.py

cat <<EOF

✓ Started.
   DB:       localhost:5433  (db service_droid, user service_droid_app)
   Logs:     tail -f .dev/bot.log
   Stop:     ./scripts/dev-stop.sh
   DB reset: ./scripts/dev-reset.sh
EOF
