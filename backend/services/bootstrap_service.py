"""بررسی آمادگی اجرای لوکال — share، دیتابیس، کاربران."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from config import (
    APP_MODE,
    APP_PORT,
    DB_CURRENT_PATH,
    INPUT_EXCEL_PATH,
    LOCAL_DATA_DIR,
    SHARED_DATA_DIR,
    USERS_PATH,
)
from local_config import CONFIG_FILE, EXAMPLE_CONFIG_FILE


def _path_accessible(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _path_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test = path / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _user_count() -> int:
    from services.user_service import _db_users_enabled, _load_users, count_users_in_db

    if _db_users_enabled():
        from db.connection import get_db_manager

        with get_db_manager().connect(write=False) as conn:
            return count_users_in_db(conn)
    if USERS_PATH.exists():
        return len(_load_users())
    return 0


def get_setup_status() -> Dict[str, Any]:
    """Simplified setup check.
    With the new model: db/db_current.db + admin-created users is enough.
    No share.config or external seed is required anymore.
    """
    from config import DB_TEMPLATE_PATH, PRIMARY_DATA_DIR

    primary_accessible = _path_accessible(PRIMARY_DATA_DIR)
    db_exists = _path_accessible(DB_CURRENT_PATH)
    template_exists = DB_TEMPLATE_PATH.exists()
    users_count = _user_count()
    users_ready = users_count > 0
    config_exists = CONFIG_FILE.exists()

    messages: List[str] = []
    if not db_exists and template_exists:
        messages.append("Using template DB from db/db_current.db (will copy on first admin config).")
    if not users_ready:
        messages.append("No users in DB yet — default admin should be present in template. Use admin panel to add more.")
    if not primary_accessible:
        messages.append(f"Primary data dir not yet accessible: {PRIMARY_DATA_DIR}")

    ready = db_exists and users_ready
    login_ok = users_ready or template_exists  # allow login with template admin

    return {
        "ready": ready,
        "login_ok": login_ok,
        "mode": APP_MODE,
        "port": APP_PORT,
        "config_file": str(CONFIG_FILE),
        "config_exists": config_exists,
        "primary_data_dir": str(PRIMARY_DATA_DIR),
        "shared_data_dir": str(SHARED_DATA_DIR),
        "local_data_dir": str(LOCAL_DATA_DIR),
        "database_path": str(DB_CURRENT_PATH),
        "database_exists": db_exists,
        "template_db": str(DB_TEMPLATE_PATH),
        "template_exists": template_exists,
        "input_excel_exists": INPUT_EXCEL_PATH.exists(),
        "input_excel_path": str(INPUT_EXCEL_PATH),
        "users_path": str(USERS_PATH),
        "users_ready": users_ready,
        "users_count": users_count,
        "messages": messages,
    }


def ensure_local_runtime() -> Dict[str, Any]:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    from services.user_service import init_users

    init_users()
    return get_setup_status()