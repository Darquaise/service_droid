#!/usr/bin/env bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$BASE_DIR/.venv/bin/activate"

RESTART_CODE=42

while true; do
    python3 "$BASE_DIR/main.py"
    code=$?

    if [ "$code" -eq "$RESTART_CODE" ]; then
        echo "[service_droid] Bot requested restart (exit code $code). Restarting in 3s..."
        sleep 3
    else
        echo "[service_droid] Bot exited with code $code. Not restarting."
        break
    fi
done
