#!/usr/bin/env bash
#
# Runs the end-to-end tests against the real test Discord guild, with a throwaway Postgres.
#   - Postgres in Docker (compose.e2e.yml, tmpfs, own port) — the local dev DB is never touched
#   - schema via Alembic (same as production)
#   - pytest backend/e2e with the settings from .env.e2e; extra arguments go to pytest
#
# Usage:   ./scripts/e2e.sh                 # everything
#          ./scripts/e2e.sh -k galatron     # a subset
# Setup:   see docs/testing.md (test application, test guild, dummy bots, .env.e2e)
#
# After a full green run (no extra arguments) the code's fingerprint is stored in .dev/e2e-passed; the pre-push hook
# skips its rerun when the code is still bit-identical (scripts/e2e-fingerprint.sh).
#
# Only one run per machine at a time (the bot token can only log in once, whichever checkout runs):
# guarded by ~/.cache/service_droid/e2e.lock, which the tests verify (backend/e2e/harness/env.py).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.dev"
LOCK_DIR="$HOME/.cache/service_droid/e2e.lock"
# -p wins over COMPOSE_PROJECT_NAME from .env, which would otherwise point this at the dev DB's project
COMPOSE=(docker compose -p service-droid-e2e -f "$ROOT/compose.e2e.yml")
E2E_DB_PORT="${E2E_DB_PORT:-5434}"
export E2E_DB_PORT
E2E_DB_URL="postgresql+psycopg://service_droid_e2e:service_droid_e2e@localhost:${E2E_DB_PORT}/service_droid_e2e"

for tool in docker uv; do
  command -v "$tool" >/dev/null 2>&1 || { echo "✗ '$tool' not found."; exit 1; }
done
docker info >/dev/null 2>&1 || { echo "✗ Docker daemon is not running (e.g. 'colima start')."; exit 1; }

if [ ! -f "$ROOT/.env.e2e" ]; then
  echo "✗ .env.e2e is missing."
  echo "  cp .env.e2e.example .env.e2e  and fill it in — the one-time Discord setup is in docs/testing.md."
  exit 1
fi

[ -d "$ROOT/backend/.venv" ] || ( echo "▶ uv sync (one-off)…"; cd "$ROOT/backend" && uv sync )

# The local dev bot (scripts/dev-start.sh) may use the same token; two sessions would both answer.
if [ -f "$RUN_DIR/bot.pid" ] && kill -0 "$(cat "$RUN_DIR/bot.pid" 2>/dev/null)" 2>/dev/null; then
  echo "✗ The local dev bot is running (PID $(cat "$RUN_DIR/bot.pid")) — stop it first: ./scripts/dev-stop.sh"
  exit 1
fi

# --- one run at a time ---------------------------------------------------------------------
mkdir -p "$RUN_DIR" "$(dirname "$LOCK_DIR")"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  other="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$other" ] && kill -0 "$other" 2>/dev/null; then
    echo "✗ Another e2e run is active (PID $other). The test bot can only be logged in once."
    exit 1
  fi
  echo "▶ Removing a stale lock from a crashed run."
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
fi
echo $$ >"$LOCK_DIR/pid"

cleanup() {
  echo "▶ Stopping the test database…"
  "${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
  rm -rf "$LOCK_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

FINGERPRINT="$("$ROOT/scripts/e2e-fingerprint.sh")"

# --- database ------------------------------------------------------------------------------
echo "▶ Throwaway database (Docker, port $E2E_DB_PORT)…"
"${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
"${COMPOSE[@]}" up -d --wait

echo "▶ Database migrations (alembic upgrade head)…"
( cd "$ROOT/backend" && env DATABASE_URL="$E2E_DB_URL" uv run alembic upgrade head )

# --- tests ---------------------------------------------------------------------------------
# DATABASE_URL is a real env var, so it wins over anything a .env file says.
# E2E_REQUIRED turns "not configured" from a skip into a failure.
echo "▶ pytest e2e…"
set +e
( cd "$ROOT/backend" && env DATABASE_URL="$E2E_DB_URL" E2E_REQUIRED=1 E2E_RUNNER_PID=$$ uv run pytest e2e "$@" )
code=$?
set -e

if [ "$code" -eq 0 ]; then
  echo "✓ e2e passed."
  # only a full run counts, and only if the code did not change while it ran
  if [ "$#" -eq 0 ] && [ "$("$ROOT/scripts/e2e-fingerprint.sh")" = "$FINGERPRINT" ]; then
    echo "$FINGERPRINT" >"$RUN_DIR/e2e-passed"
  fi
else
  echo "✗ e2e failed (exit $code)."
fi
exit "$code"
