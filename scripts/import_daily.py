#!/usr/bin/env python3
"""اجرای import روزانه — برای Task Scheduler / cron.

Usage:
  python3 scripts/import_daily.py
  python3 scripts/import_daily.py --input /share/data/input.xlsx
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import daily Excel into shared SQLite DB")
    parser.add_argument("--input", help="مسیر input.xlsx (اختیاری)")
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