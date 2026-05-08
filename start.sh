#!/bin/bash

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO"
mkdir -p "$REPO/logs"
screen -AmdS service_droid "$REPO/.start.sh"
