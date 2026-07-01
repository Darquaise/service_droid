#!/usr/bin/env bash
#
# Stops the local stack: the bot and the local Postgres.
# The local DB data is preserved (the volume is not removed).
#
#   ./scripts/dev-stop.sh
#
# Wipe the DB entirely (delete data): ./scripts/dev-reset.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="$ROOT/.dev"

# Terminates a process together with all its children (uv wrapper, python, …).
kill_tree() {
  local pid="$1" child
  [ -n "$pid" ] || return 0
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

stop_proc() {
  local name="$1"
  local pidfile="$RUN_DIR/$name.pid" pid
  [ -f "$pidfile" ] || return 0
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "▶ Stopping $name (PID $pid)…"
    kill_tree "$pid"
  fi
  rm -f "$pidfile"
}

stop_proc bot

echo "▶ Stopping database (data is preserved)…"
docker compose -f compose.dev.yml down

echo "✓ Stopped."
