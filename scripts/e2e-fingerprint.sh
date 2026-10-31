#!/usr/bin/env bash
#
# Prints a hash of everything a live e2e run depends on (backend/, scripts/e2e.sh, compose.e2e.yml) as it is in
# the working tree right now: tracked and untracked files, minus what .gitignore excludes. Equal hash = bit-identical
# code. scripts/e2e.sh stores it after a full green run, .githooks/pre-push compares against it to skip a rerun.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# A throwaway index keeps the real one (and what is staged) untouched.
index="$(mktemp -u)"
trap 'rm -f "$index"' EXIT
GIT_INDEX_FILE="$index" git add -A -- backend scripts/e2e.sh compose.e2e.yml
GIT_INDEX_FILE="$index" git write-tree
