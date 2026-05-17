#!/usr/bin/env bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$BASE_DIR/.env" ]; then
    echo "[service_droid] ERROR: $BASE_DIR/.env not found. Copy .env.example to .env and fill in DISCORD_TOKEN." >&2
    exit 1
fi

set -a
source "$BASE_DIR/.env"
set +a

source "$BASE_DIR/.venv/bin/activate"

export PYTHONUNBUFFERED=1

echo "[service_droid] installing/updating dependencies from requirements.txt..."
pip install -r "$BASE_DIR/requirements.txt"

LOG_DIR="$BASE_DIR/logs"
LATEST="$LOG_DIR/latest.log"
START_FILE="$LOG_DIR/.latest_start"
RESTART_CODE=42

mkdir -p "$LOG_DIR"

rotate_log() {
    if [ -s "$LATEST" ]; then
        local end_ts start_ts
        end_ts=$(date -r "$LATEST" '+%Y-%m-%d_%H-%M-%S')
        if [ -s "$START_FILE" ]; then
            start_ts=$(cat "$START_FILE")
        else
            start_ts="$end_ts"
        fi
        mv "$LATEST" "$LOG_DIR/${start_ts}__${end_ts}.log"
    elif [ -f "$LATEST" ]; then
        rm -f "$LATEST"
    fi
    date '+%Y-%m-%d_%H-%M-%S' > "$START_FILE"
    : > "$LATEST"
}

while true; do
    rotate_log
    python3 -u "$BASE_DIR/main.py" 2>&1 | tee -a "$LATEST"
    code=${PIPESTATUS[0]}

    if [ "$code" -eq "$RESTART_CODE" ]; then
        echo "[service_droid] Bot requested restart (exit code $code). Restarting in 3s..." | tee -a "$LATEST"
        sleep 3
    else
        echo "[service_droid] Bot exited with code $code. Not restarting." | tee -a "$LATEST"
        break
    fi
done
