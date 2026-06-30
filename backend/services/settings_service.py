"""تنظیمات مسیر فایل‌ها — فقط سوپر‌یوزر (admin)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config import (
    BASE_DIR,
    DATA_DIR,
    DB_CURRENT_PATH,
    DB_NEW_PATH,
    DB_OLD_PATH,
    DB_TEMPLATE_PATH,
    INPUT_EXCEL_PATH,
    LOCAL_DATA_DIR,
    LOCAL_EXCEL_PATH,
    LOCK_FLAG_PATH,
    LOGS_DIR,
    OUTPUT_EXCEL_PATH,
    SHARED_DATA_DIR,
    USERS_PATH,
)

SETTINGS_PATH = LOCAL_DATA_DIR / "system_settings.json"

ALLOWED_KEYS = (
    "primary_data_dir",
    "shared_data_dir",
    "local_data_dir",
    "input_excel",
    "output_excel",
    "db_current",
    "db_new",
    "db_old",
    "lock_flag",
    "logs_dir",
    "users_file",
    "local_excel_legacy",
)

PATH_GROUPS = (
    {
        "id": "primary",
        "title": "مکان اصلی داده (جدید - ساده شده)",
        "description": "پوشه‌ای که db_current.db و فایل اکسل ورودی آنجا قرار می‌گیرند. اولویت اول سیستم.",
        "fields": [
            ("primary_data_dir", "پوشه داده اصلی (Data Folder)", "dir"),
        ],
    },
    {
        "id": "share",
        "title": "پوشه Share مشترک (اختیاری - قدیمی)",
        "description": "برای سازگاری با تنظیمات قبلی",
        "fields": [
            ("shared_data_dir", "پوشه داده مشترک (Share)", "dir"),
            ("local_data_dir", "پوشه داده محلی کلاینت", "dir"),
        ],
    },
    {
        "id": "excel",
        "title": "اکسل ورودی و خروجی",
        "description": "فایل روزانه ERP و خروجی export سامانه",
        "fields": [
            ("input_excel", "اکسل ورودی (import روزانه)", "file"),
            ("output_excel", "اکسل خروجی", "file"),
            ("local_excel_legacy", "اکسل محلی قدیمی (مهاجرت)", "file"),
        ],
    },
    {
        "id": "database",
        "title": "پایگاه داده و پشتیبان",
        "description": "db_current فعال · db_new staging · db_old نسخه پشتیبان هنگام swap",
        "fields": [
            ("db_current", "پایگاه فعال (db_current.db)", "file"),
            ("db_new", "پایگاه staging (db_new.db)", "file"),
            ("db_old", "پشتیبان قبلی (db_old.db)", "file"),
        ],
    },
    {
        "id": "system",
        "title": "سیستم و کاربران",
        "description": "قفل swap، لاگ import و فایل کاربران",
        "fields": [
            ("lock_flag", "فایل قفل swap (lock.flag)", "file"),
            ("logs_dir", "پوشه لاگ‌ها", "dir"),
            ("users_file", "فایل کاربران (users.json)", "file"),
        ],
    },
)


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _find_root_excel() -> Optional[Path]:
    """Look for user-dropped Excel in project root."""
    for name in ("input.xlsx", "رضوانی نهایی.xlsx", "purchases.xlsx"):
        p = (BASE_DIR / name)
        if p.exists():
            return p
    return None


def ensure_data_location_ready(data_dir: str) -> Dict[str, Any]:
    """When admin sets a data folder:
    - Create it
    - Copy DB template from db/db_current.db if no DB present
    - Copy Excel from root if no Excel present in target
    This fulfills: 'DB and Excel are stored next to each other in the chosen location'
    """
    target = Path(data_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    result = {"data_dir": str(target), "db_copied": False, "excel_copied": False}

    # DB: copy template if missing
    target_db = target / "db_current.db"
    if not target_db.exists() and DB_TEMPLATE_PATH.exists():
        shutil.copy2(DB_TEMPLATE_PATH, target_db)
        result["db_copied"] = True

    # Also prepare siblings for swap files (they will be created on import)
    for extra in ("db_new.db", "db_old.db", "lock.flag"):
        (target / extra).parent.mkdir(parents=True, exist_ok=True)

    # Excel: if no input in target, copy from root
    target_excel = target / "input.xlsx"
    if not target_excel.exists():
        root_excel = _find_root_excel()
        if root_excel:
            shutil.copy2(root_excel, target_excel)
            result["excel_copied"] = True
            result["excel_source"] = str(root_excel)

    # logs
    (target / "logs").mkdir(exist_ok=True)

    return result


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    return f"{round(size_bytes / (1024 * 1024), 2)} MB"


def _path_status(path: Path, kind: str) -> Dict[str, Any]:
    exists = path.exists()
    info: Dict[str, Any] = {
        "path": str(path),
        "kind": kind,
        "exists": exists,
        "size_bytes": 0,
        "size_human": "—",
        "modified_at": None,
    }
    if not exists:
        return info
    try:
        if kind == "dir" or path.is_dir():
            info["kind"] = "dir"
            info["size_human"] = "پوشه"
        else:
            st = path.stat()
            info["size_bytes"] = int(st.st_size)
            info["size_human"] = _format_size(info["size_bytes"])
            info["modified_at"] = datetime.fromtimestamp(st.st_mtime).isoformat()
    except OSError:
        pass
    return info


def default_paths_from_share(share_dir: str) -> Dict[str, str]:
    root = Path(share_dir.strip()).resolve()
    return {
        "shared_data_dir": str(root),
        "input_excel": str(root / "input.xlsx"),
        "output_excel": str(root / "output.xlsx"),
        "db_current": str(root / "db_current.db"),
        "db_new": str(root / "db_new.db"),
        "db_old": str(root / "db_old.db"),
        "lock_flag": str(root / "lock.flag"),
        "logs_dir": str(root / "logs"),
    }


def get_paths_overview() -> Dict[str, Any]:
    """مسیرهای مؤثر + وضعیت هر فایل/پوشه برای پنل سوپر‌یوزر."""
    from db.connection import get_db_manager, is_system_locked
    from services import excel_service

    paths = get_effective_paths()
    groups = []
    for group in PATH_GROUPS:
        items = []
        for key, label, kind in group["fields"]:
            p = Path(paths.get(key) or "")
            items.append({
                "key": key,
                "label": label,
                "kind": kind,
                **_path_status(p, kind),
            })
        groups.append({
            "id": group["id"],
            "title": group["title"],
            "description": group["description"],
            "items": items,
        })

    db_info = {}
    try:
        db_info = get_db_manager().db_info()
    except Exception as exc:
        db_info = {"error": str(exc)}

    return {
        "paths": paths,
        "groups": groups,
        "runtime": {
            "locked": is_system_locked(),
            "storage": excel_service.excel_info(),
            "database": db_info,
        },
    }


def get_effective_paths() -> Dict[str, str]:
    s = load_settings()
    primary = s.get("primary_data_dir")
    if not primary:
        try:
            import config as cfg
            primary = str(getattr(cfg, "PRIMARY_DATA_DIR", SHARED_DATA_DIR))
        except Exception:
            primary = str(SHARED_DATA_DIR)
    return {
        "primary_data_dir": primary,
        "shared_data_dir": s.get("shared_data_dir") or str(SHARED_DATA_DIR),
        "local_data_dir": s.get("local_data_dir") or str(LOCAL_DATA_DIR),
        "input_excel": s.get("input_excel") or str(INPUT_EXCEL_PATH),
        "output_excel": s.get("output_excel") or str(OUTPUT_EXCEL_PATH),
        "db_current": s.get("db_current") or str(DB_CURRENT_PATH),
        "db_new": s.get("db_new") or str(DB_NEW_PATH),
        "db_old": s.get("db_old") or str(DB_OLD_PATH),
        "lock_flag": s.get("lock_flag") or str(LOCK_FLAG_PATH),
        "logs_dir": s.get("logs_dir") or str(LOGS_DIR),
        "users_file": s.get("users_file") or str(USERS_PATH),
        "local_excel_legacy": s.get("local_excel_legacy") or str(LOCAL_EXCEL_PATH),
        "settings_file": str(SETTINGS_PATH),
        "updated_at": s.get("updated_at"),
        "updated_by": s.get("updated_by"),
    }


def apply_runtime_paths() -> Dict[str, str]:
    """اعمال مسیرهای ذخیره‌شده روی config (بدون نیاز به ری‌استارت)."""
    import config as cfg
    from db.connection import reset_db_manager

    s = load_settings()
    if not s:
        return get_effective_paths()

    def _p(key: str, fallback: Path) -> Path:
        val = s.get(key)
        return Path(val).resolve() if val else fallback

    if s.get("primary_data_dir"):
        pdir = Path(s["primary_data_dir"]).resolve()
        cfg.DATA_DIR = pdir
        cfg.SHARED_DATA_DIR = pdir
        cfg.PRIMARY_DATA_DIR = pdir
        # Re-resolve DB and Excel to the new primary
        cfg.DB_CURRENT_PATH = pdir / "db_current.db"
        cfg.DB_NEW_PATH = pdir / "db_new.db"
        cfg.DB_OLD_PATH = pdir / "db_old.db"
        cfg.INPUT_EXCEL_PATH = pdir / "input.xlsx"
        cfg.EXCEL_PATH = cfg.INPUT_EXCEL_PATH
    if s.get("shared_data_dir"):
        cfg.DATA_DIR = Path(s["shared_data_dir"]).resolve()
        cfg.SHARED_DATA_DIR = cfg.DATA_DIR
    if s.get("local_data_dir"):
        cfg.LOCAL_DATA_DIR = Path(s["local_data_dir"]).resolve()

    cfg.INPUT_EXCEL_PATH = _p("input_excel", cfg.INPUT_EXCEL_PATH)
    cfg.SOURCE_EXCEL_PATH = cfg.INPUT_EXCEL_PATH
    cfg.EXCEL_PATH = cfg.INPUT_EXCEL_PATH
    cfg.OUTPUT_EXCEL_PATH = _p("output_excel", cfg.OUTPUT_EXCEL_PATH)
    cfg.DB_CURRENT_PATH = _p("db_current", cfg.DB_CURRENT_PATH)
    cfg.DB_NEW_PATH = _p("db_new", cfg.DB_NEW_PATH)
    cfg.DB_OLD_PATH = _p("db_old", cfg.DB_OLD_PATH)
    cfg.LOCK_FLAG_PATH = _p("lock_flag", cfg.LOCK_FLAG_PATH)
    cfg.LOGS_DIR = _p("logs_dir", cfg.LOGS_DIR)
    cfg.USERS_PATH = _p("users_file", cfg.USERS_PATH)
    cfg.LOCAL_EXCEL_PATH = _p("local_excel_legacy", cfg.LOCAL_EXCEL_PATH)

    for p in (cfg.DATA_DIR, cfg.LOCAL_DATA_DIR, cfg.LOGS_DIR):
        p.mkdir(parents=True, exist_ok=True)

    reset_db_manager()
    return get_effective_paths()


def save_settings(updates: Dict[str, Any], username: str) -> Dict[str, Any]:
    clean = {k: str(v).strip() for k, v in updates.items() if k in ALLOWED_KEYS and str(v).strip()}
    if not clean:
        raise ValueError("مسیر معتبری ارسال نشد")

    prep_info = {}
    for key, val in clean.items():
        p = Path(val)
        if key in ("primary_data_dir", "shared_data_dir", "logs_dir") or key.endswith("_dir"):
            p.mkdir(parents=True, exist_ok=True)
            if key in ("primary_data_dir", "shared_data_dir"):
                prep_info = ensure_data_location_ready(str(p))
        elif key == "input_excel" and not p.exists():
            raise ValueError(f"فایل ورودی یافت نشد: {val}")

    current = load_settings()
    current.update(clean)
    if prep_info:
        current["last_prep"] = prep_info
    current["updated_at"] = _utc_now()
    current["updated_by"] = username
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    apply_runtime_paths()
    return get_effective_paths()