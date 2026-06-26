"""راه‌اندازی اولیه پوشه share — کپی DB آماده و seed کاربران."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config import BASE_DIR, DB_CURRENT_PATH, LOGS_DIR, SHARED_DATA_DIR
from db.connection import get_db_manager
from db.schema import USERS_DDL
from services.user_service import _hash_password, count_users_in_db

logger = logging.getLogger("tadarokat.share_init")

TEMPLATE_DB = BASE_DIR / "templates" / "db_current.db"
SEED_FILENAME = "share_users.seed.json"
PLACEHOLDER_PASSWORDS = frozenset({"", "CHANGE_ME", "CHANGE_ME_STRONG_PASSWORD"})


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _ensure_share_dirs() -> None:
    SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _build_template_db() -> None:
    from db.connection import DatabaseManager
    from db.schema import all_ddl

    TEMPLATE_DB.parent.mkdir(parents=True, exist_ok=True)
    if TEMPLATE_DB.exists():
        TEMPLATE_DB.unlink()
    mgr = DatabaseManager(TEMPLATE_DB)
    with mgr.connect(write=True) as conn:
        for ddl in all_ddl():
            conn.executescript(ddl)
        mgr._set_meta(conn, "template_version", "1")
        mgr._set_meta(conn, "share_initialized", "0")


def _copy_template_db() -> bool:
    if DB_CURRENT_PATH.exists():
        return False
    if not TEMPLATE_DB.exists():
        _build_template_db()
    shutil.copy2(TEMPLATE_DB, DB_CURRENT_PATH)
    return True


def _find_seed_file() -> Path | None:
    candidates = [
        SHARED_DATA_DIR / SEED_FILENAME,
        BASE_DIR / SEED_FILENAME,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _load_seed_users(seed_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    users = data.get("users") if isinstance(data, dict) else data
    if not isinstance(users, list) or not users:
        raise ValueError("فایل seed باید آرایه users داشته باشد")
    return users


def seed_users_from_file(seed_path: Path, *, remove_after: bool = True) -> int:
    raw_users = _load_seed_users(seed_path)
    now = _utc_now()
    inserted = 0
    mgr = get_db_manager()

    with mgr.connect(write=True) as conn:
        conn.executescript(USERS_DDL)
        existing = count_users_in_db(conn)
        if existing > 0:
            return 0

        for item in raw_users:
            username = str(item.get("username") or "").strip().lower()
            password = str(item.get("password") or "").strip()
            name = str(item.get("name") or "").strip()
            role = str(item.get("role") or "expert").strip()
            if not username or not password or not name:
                raise ValueError(f"کاربر ناقص در seed: {item}")
            if password in PLACEHOLDER_PASSWORDS:
                raise ValueError(f"رمز کاربر {username} هنوز تنظیم نشده (CHANGE_ME)")

            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, name, role, expert, warehouse, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    username,
                    _hash_password(password),
                    name,
                    role,
                    item.get("expert"),
                    item.get("warehouse"),
                    1 if item.get("active", True) else 0,
                    now,
                    now,
                ),
            )
            inserted += 1

        mgr._set_meta(conn, "share_initialized", _utc_now())
        mgr._set_meta(conn, "users_seeded", str(inserted))
        mgr.bump_version(conn)

    if remove_after:
        seed_path.unlink(missing_ok=True)
        logger.info("seed file removed: %s", seed_path)

    return inserted


def initialize_share(*, require_seed: bool = True) -> Dict[str, Any]:
    """کپی DB آماده روی share و seed کاربران از فایل امن."""
    _ensure_share_dirs()
    created = _copy_template_db()
    seed_path = _find_seed_file()
    seeded = 0
    messages: List[str] = []

    mgr = get_db_manager()
    with mgr.connect(write=True) as conn:
        conn.executescript(USERS_DDL)
        user_count = count_users_in_db(conn)

    if user_count == 0:
        if not seed_path:
            msg = (
                f"کاربری در DB نیست. فایل {SEED_FILENAME} را در share قرار دهید "
                f"(نمونه: share_users.seed.example.json) و دوباره init_share را اجرا کنید."
            )
            if require_seed:
                raise FileNotFoundError(msg)
            messages.append(msg)
        else:
            seeded = seed_users_from_file(seed_path, remove_after=True)
            messages.append(f"{seeded} کاربر از seed وارد شد — فایل seed حذف شد.")

    return {
        "ok": True,
        "database_created": created,
        "database_path": str(DB_CURRENT_PATH),
        "users_seeded": seeded,
        "user_count": user_count + seeded,
        "messages": messages,
    }