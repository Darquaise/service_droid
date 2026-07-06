#!/usr/bin/env bash
#
# Resets the local dev database: deletes ALL local DB data (the volume) and
# brings the stack back up with a fresh, empty schema.
#
#   ./scripts/dev-reset.sh         # asks for confirmation first
#   ./scripts/dev-reset.sh -y      # no prompt (e.g. for scripts)
#
# Affects only the LOCAL dev DB (compose.dev.yml). Production is left untouched.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

if [ "${1:-}" != "-y" ] && [ "${1:-}" != "--yes" ]; then
  printf "⚠ Deletes ALL local dev DB data. Continue? [y/N] "
  read -r answer || answer=""
  case "$answer" in
    y | Y) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

# 1) Stop running processes + DB container (volume stays for now).
"$DIR/dev-stop.sh"

# 2) Remove the DB volume → all data gone.
echo "▶ Removing DB volume…"
docker compose -f "$ROOT/compose.dev.yml" down -v >/dev/null 2>&1 || true

# 3) Bring it back up fresh (creates the schema anew).
echo "▶ Starting with a fresh database…"
echo
exec "$DIR/dev-start.sh"
