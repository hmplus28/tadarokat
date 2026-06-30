#!/usr/bin/env python3
"""اجرای import روزانه — برای Task Scheduler / cron.

Usage:
  python3 scripts/import_daily.py
  python3 scripts/import_daily.py --input /share/data/input.xlsx
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from pathlib import Path

# Force UTF-8 console output on Windows (fixes Persian/garbled characters in PowerShell/CMD)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import daily Excel into shared SQLite DB")
    parser.add_argument("--input", help="Path to input.xlsx (optional)")
    args = parser.parse_args()

    from db.import_service import run_import

    try:
        result = run_import(args.input)
        print("OK", result)
        return 0
    except Exception as exc:
        logging.exception("Import failed")
        print("FAIL", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())