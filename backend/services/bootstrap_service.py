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
    share_accessible = _path_accessible(SHARED_DATA_DIR)
    share_writable = _path_writable(SHARED_DATA_DIR) if share_accessible else False
    db_exists = _path_accessible(DB_CURRENT_PATH)
    users_count = _user_count()
    users_ready = users_count > 0
    config_exists = CONFIG_FILE.exists()

    messages: List[str] = []
    if not config_exists:
        messages.append(
            f"فایل share.config.json یافت نشد — از {EXAMPLE_CONFIG_FILE.name} کپی بگیرید."
        )
    if not share_accessible:
        messages.append(f"پوشه share در دسترس نیست: {SHARED_DATA_DIR}")
    elif not db_exists:
        messages.append(
            "پایگاه share هنوز ساخته نشده — یک بار scripts/init_share را روی share اجرا کنید."
        )
    elif not users_ready:
        messages.append(
            "کاربری در پایگاه نیست — share_users.seed.json را در share بگذارید و init_share را اجرا کنید."
        )

    ready = share_accessible and db_exists and users_ready
    login_ok = users_ready

    return {
        "ready": ready,
        "login_ok": login_ok,
        "mode": APP_MODE,
        "port": APP_PORT,
        "config_file": str(CONFIG_FILE),
        "config_exists": config_exists,
        "shared_data_dir": str(SHARED_DATA_DIR),
        "local_data_dir": str(LOCAL_DATA_DIR),
        "database_path": str(DB_CURRENT_PATH),
        "database_exists": db_exists,
        "input_excel_exists": INPUT_EXCEL_PATH.exists(),
        "users_path": str(USERS_PATH),
        "users_ready": users_ready,
        "users_count": users_count,
        "share_accessible": share_accessible,
        "share_writable": share_writable,
        "messages": messages,
    }


def ensure_local_runtime() -> Dict[str, Any]:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    from services.user_service import init_users

    init_users()
    return get_setup_status()