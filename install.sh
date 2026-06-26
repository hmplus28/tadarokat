#!/usr/bin/env bash
# نصب اولیه سامانه تدارکات — یک بار روی هر سیستم
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
QUIET=0
if [[ "${1:-}" == "--quiet" ]]; then QUIET=1; fi

echo "══════════════════════════════════════════"
echo "  سامانه تدارکات — نصب اولیه (لوکال + Share)"
echo "══════════════════════════════════════════"
echo ""

# ── ۱. فایل تنظیم share ──
if [ ! -f "share.config.json" ]; then
  echo "📄 ایجاد share.config.json ..."
  cp share.config.example.json share.config.json
  if [ "$QUIET" -eq 0 ]; then
    echo ""
    echo "⚠ مسیر share را در share.config.json تنظیم کنید"
    read -r -p "مسیر پوشه share (Enter برای ./data محلی): " SHARE_PATH
    if [ -n "$SHARE_PATH" ]; then
      python3 -c "
import json
from pathlib import Path
p = Path('share.config.json')
cfg = json.loads(p.read_text(encoding='utf-8'))
cfg['shared_data_dir'] = '''$SHARE_PATH'''
p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
"
      echo "✓ shared_data_dir تنظیم شد"
    fi
  fi
else
  echo "✓ share.config.json موجود است"
fi

# ── ۲. محیط مجازی Python ──
PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "❌ python3 یافت نشد"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "🐍 ایجاد محیط مجازی Python ..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip -q
python -m pip install -r backend/requirements.txt -q
echo "✓ وابستگی‌های Python"

# ── ۳. پایگاه آماده share ──
python scripts/build_db_template.py

# ── ۴. فایل‌های آفلاین فرانت‌اند ──
if [ ! -f "frontend/vendor/tailwind.css" ] && [ -f "scripts/download_vendor.sh" ]; then
  bash scripts/download_vendor.sh
else
  echo "✓ فایل‌های vendor"
fi

# ── ۵. پوشه share ──
SHARE_DIR="$(python -c "
import json
from pathlib import Path
cfg = json.loads(Path('share.config.json').read_text(encoding='utf-8'))
print(cfg.get('shared_data_dir', './data'))
")"
mkdir -p "$SHARE_DIR/logs" 2>/dev/null || echo "⚠ پوشه share فعلاً در دسترس نیست: $SHARE_DIR"

date -Iseconds > .installed 2>/dev/null || date > .installed
chmod +x run.sh scripts/init_share.sh scripts/launcher.py 2>/dev/null || true

echo ""
echo "══════════════════════════════════════════"
echo "  ✓ نصب کامل شد"
echo "══════════════════════════════════════════"
echo ""
echo "  اجرا:        ./run.sh"
echo "  تنظیم share: share.config.json"
echo "  راه‌اندازی:  ./scripts/init_share.sh"
echo "  import خودکار: پنل admin → Import خودکار (ساعت ۸)"
echo ""