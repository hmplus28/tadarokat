#!/usr/bin/env bash
# Daily Excel import - run on one central machine or Windows Task Scheduler
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f "share.config.json" ]; then
  echo "[ERROR] share.config.json not found - configure share path first."
  exit 1
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec python scripts/import_daily.py "$@"