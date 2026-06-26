#!/usr/bin/env bash
# Import روزانه — روی یک ماشین مرکزی یا Task Scheduler ویندوز اجرا شود
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f "share.config.json" ]; then
  echo "❌ share.config.json یافت نشد — مسیر share را تنظیم کنید."
  exit 1
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export TADAROKAT_MODE=import
export TADAROKAT_STORAGE=sqlite

python scripts/import_daily.py "$@"