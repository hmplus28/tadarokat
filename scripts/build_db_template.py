#!/usr/bin/env python3
"""ساخت فایل پایگاه آماده (فقط schema) برای کپی روی share."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from db.connection import DatabaseManager  # noqa: E402
from db.schema import USERS_DDL, all_ddl  # noqa: E402

TEMPLATE_DIR = ROOT / "templates"
TEMPLATE_DB = TEMPLATE_DIR / "db_current.db"


def build() -> Path:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    if TEMPLATE_DB.exists():
        TEMPLATE_DB.unlink()
    mgr = DatabaseManager(TEMPLATE_DB)
    with mgr.connect(write=True) as conn:
        for ddl in all_ddl():
            conn.executescript(ddl)
        conn.executescript(USERS_DDL)
        mgr._set_meta(conn, "template_version", "1")
        mgr._set_meta(conn, "share_initialized", "0")
    print(f"✓ {TEMPLATE_DB}")
    return TEMPLATE_DB


if __name__ == "__main__":
    build()