#!/usr/bin/env python3
"""ساخت فایل پایگاه آماده (فقط schema) برای کپی روی share."""

from __future__ import annotations

import io
import os
import shutil
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

from db.connection import DatabaseManager  # noqa: E402
from db.schema import USERS_DDL, all_ddl, seed_categories, GOODS_CATEGORIES  # noqa: E402
from passlib.context import CryptContext
import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)

DB_DIR = ROOT / "db"
TEMPLATE_DB = DB_DIR / "db_current.db"


def build() -> Path:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if TEMPLATE_DB.exists():
        TEMPLATE_DB.unlink()
    mgr = DatabaseManager(TEMPLATE_DB)
    with mgr.connect(write=True) as conn:
        for ddl in all_ddl():
            conn.executescript(ddl)
        conn.executescript(USERS_DDL)

        # Seed users directly (no seed files anymore)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        users = [
            ("admin", "admin123", "مدیر سیستم", "admin", None, None),
            ("mostafa", "mostafa123", "مصطفی رضوانی", "expert", "مصطفی رضوانی", None),
            ("fabri", "fabri123", "فریبا صالح آبادی", "expert", "فریبا صالح آبادی", None),
            ("behnaz", "behnaz123", "بهناز عظیمی", "expert", "بهناز عظیمی", None),
            ("manager", "manager123", "مدیر تدارکات", "manager", None, None),
            ("anbar", "anbar123", "مسئول انبار مصرفی", "warehouse", None, "انبار مصرفی"),
        ]

        for username, password, name, role, expert, warehouse in users:
            conn.execute(
                """
                INSERT OR REPLACE INTO users 
                (id, username, password_hash, name, role, expert, warehouse, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    f"user-{username}",
                    username,
                    _hash_password(password),
                    name,
                    role,
                    expert,
                    warehouse,
                    now,
                ),
            )

        # Seed goods categories
        seed_categories(conn)

        mgr._set_meta(conn, "template_version", "2")
        mgr._set_meta(conn, "categories_seeded", "1")
        mgr._set_meta(conn, "default_admin_seeded", "1")
    print(f"[OK] Template DB created: {TEMPLATE_DB}")
    print("  Users created (username / password):")
    print("    - admin / admin123")
    print("    - mostafa / mostafa123")
    print("    - fabri / fabri123")
    print("    - behnaz / behnaz123")
    print("    - manager / manager123")
    print("    - anbar / anbar123")
    print(f"  Categories: {', '.join(GOODS_CATEGORIES)}")
    return TEMPLATE_DB


if __name__ == "__main__":
    build()