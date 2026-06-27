#!/usr/bin/env bash
# Tadarokat first-time install
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
QUIET=0
if [[ "${1:-}" == "--quiet" ]]; then QUIET=1; fi

echo "=========================================="
echo "  Tadarokat - install (local + share)"
echo "=========================================="
echo ""

# -- 1. share config --
if [ ! -f "share.config.json" ]; then
  echo "-> Creating share.config.json ..."
  cp share.config.example.json share.config.json
  if [ "$QUIET" -eq 0 ]; then
    echo ""
    echo "[WARN] Set share path in share.config.json"
    read -r -p "Share folder path (Enter for local ./data): " SHARE_PATH
    if [ -n "$SHARE_PATH" ]; then
      python3 -c "
import json
from pathlib import Path
p = Path('share.config.json')
cfg = json.loads(p.read_text(encoding='utf-8'))
cfg['shared_data_dir'] = '''$SHARE_PATH'''
p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
"
      echo "[OK] shared_data_dir updated"
    fi
  fi
else
  echo "[OK] share.config.json exists"
fi

# -- 2. Python venv --
PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[ERROR] python3 not found"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "-> Creating Python virtual environment ..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip -q
python -m pip install -r backend/requirements.txt -q
echo "[OK] Python dependencies"

# -- 3. DB template --
python scripts/build_db_template.py

# -- 4. share data dir (UI uses CDN - no vendor download) --
SHARE_DIR="$(python -c "
import json
from pathlib import Path
cfg = json.loads(Path('share.config.json').read_text(encoding='utf-8'))
print(cfg.get('shared_data_dir', './data'))
")"
mkdir -p "$SHARE_DIR/logs" 2>/dev/null || echo "[WARN] Share folder not accessible yet: $SHARE_DIR"

date -Iseconds > .installed 2>/dev/null || date > .installed
chmod +x run.sh scripts/init_share.sh scripts/launcher.py 2>/dev/null || true

echo ""
echo "=========================================="
echo "  INSTALL COMPLETE"
echo "=========================================="
echo ""
echo "  Run:           ./run.sh"
echo "  Share config:  share.config.json"
echo "  Setup users:   ./scripts/init_share.sh"
echo "  Auto import:   admin panel -> scheduled import (default 08:00)"
echo ""