#!/usr/bin/env bash
#
# Restarts the local stack (= dev-stop.sh + dev-start.sh).
# The local DB data is preserved.
#
#   ./scripts/dev-restart.sh
#
# Reset the DB (delete data): ./scripts/dev-reset.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$DIR/dev-stop.sh"
echo
exec "$DIR/dev-start.sh"
