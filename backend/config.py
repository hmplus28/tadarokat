import os
from pathlib import Path

from local_config import apply_share_config, CONFIG_FILE, default_local_data_dir

apply_share_config()

BASE_DIR = Path(__file__).resolve().parent.parent

# New simplified model:
# - Primary data location can be set by admin (stored in system settings)
# - Fallback 1: db/ folder template (db/db_current.db) for zero-config installs
# - Fallback 2: ./data (old behavior)

DB_DIR = (BASE_DIR / "db").resolve()
DB_TEMPLATE_PATH = DB_DIR / "db_current.db"

def _get_primary_data_dir() -> Path:
    """Resolve the active data directory with new priority (no share.config required).
    The db/ template is the new zero-config default.
    """
    # 1. New explicit DATA_DIR env (recommended)
    env_dir = os.getenv("TADAROKAT_DATA_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    # 2. Admin configured via settings JSON
    try:
        import json
        candidates = [
            BASE_DIR / "data" / "system_settings.json",
            (BASE_DIR / ".local" / "tadarokat" / "system_settings.json"),
        ]
        for cand in candidates:
            if cand.exists():
                s = json.loads(cand.read_text(encoding="utf-8"))
                for key in ("primary_data_dir", "shared_data_dir"):
                    val = s.get(key)
                    if val:
                        return Path(val).resolve()
    except Exception:
        pass

    # 3. NEW PREFERRED DEFAULT: db/ folder template if present (new model)
    if DB_TEMPLATE_PATH.exists():
        return DB_DIR

    # 4. Legacy explicit TADAROKAT_SHARED_DATA (from old share.config) - only if not "."
    shared_env = os.getenv("TADAROKAT_SHARED_DATA")
    if shared_env:
        p = Path(shared_env).resolve()
        if str(p) != str(BASE_DIR):   # ignore trivial "." that test setups set
            return p

    # 5. Final legacy ./data
    return (BASE_DIR / "data").resolve()

PRIMARY_DATA_DIR = _get_primary_data_dir()

# Shared data dir kept for backward but now points to primary
SHARED_DATA_DIR = Path(os.getenv("TADAROKAT_SHARED_DATA", str(PRIMARY_DATA_DIR))).resolve()
LOCAL_DATA_DIR = Path(
    os.getenv("TADAROKAT_LOCAL_DATA", str(default_local_data_dir()))
).resolve()

DATA_DIR = SHARED_DATA_DIR
FRONTEND_DIR = BASE_DIR / "frontend"

# ── Excel resolution (admin path + data dir + root fallback) ──
def _resolve_excel() -> Path:
    # 1. Explicit env
    env_excel = os.getenv("TADAROKAT_INPUT_EXCEL") or os.getenv("TADAROKAT_SOURCE_EXCEL")
    if env_excel:
        p = Path(env_excel)
        if p.exists():
            return p.resolve()
    # 2. In primary data dir
    for name in ("input.xlsx", "purchases.xlsx", "رضوانی نهایی.xlsx"):
        cand = (PRIMARY_DATA_DIR / name)
        if cand.exists():
            return cand.resolve()
    # 3. Project root (user drops Excel here)
    root_cands = [
        BASE_DIR / "input.xlsx",
        BASE_DIR / "رضوانی نهایی.xlsx",
        BASE_DIR / "purchases.xlsx",
    ]
    for cand in root_cands:
        if cand.exists():
            return cand.resolve()
    # default location (may not exist yet)
    return (PRIMARY_DATA_DIR / "input.xlsx").resolve()

INPUT_EXCEL_PATH = _resolve_excel()
SOURCE_EXCEL_PATH = INPUT_EXCEL_PATH
EXCEL_PATH = INPUT_EXCEL_PATH

OUTPUT_EXCEL_PATH = Path(os.getenv("TADAROKAT_OUTPUT_EXCEL", str(DATA_DIR / "output.xlsx")))

# ── DB paths: prefer chosen primary data dir, fallback to template in db/ ──
def _resolve_db_path(name: str, env_key: str) -> Path:
    env_val = os.getenv(env_key)
    if env_val:
        return Path(env_val).resolve()
    # Admin primary dir first
    p = PRIMARY_DATA_DIR / name
    # If primary has no DB but template exists and primary == db dir, use template
    if not p.exists() and name == "db_current.db" and DB_TEMPLATE_PATH.exists():
        return DB_TEMPLATE_PATH
    return p

DB_CURRENT_PATH = _resolve_db_path("db_current.db", "TADAROKAT_DB_CURRENT")
DB_NEW_PATH = _resolve_db_path("db_new.db", "TADAROKAT_DB_NEW")
DB_OLD_PATH = _resolve_db_path("db_old.db", "TADAROKAT_DB_OLD")
LOCK_FLAG_PATH = Path(os.getenv("TADAROKAT_LOCK_FLAG", str(DATA_DIR / "lock.flag")))
LOGS_DIR = Path(os.getenv("TADAROKAT_LOGS_DIR", str(DATA_DIR / "logs")))

LOCAL_EXCEL_PATH = Path(os.getenv("TADAROKAT_LOCAL_EXCEL", str(LOCAL_DATA_DIR / "local_changes.xlsx")))
USERS_PATH = Path(os.getenv("TADAROKAT_USERS", str(LOCAL_DATA_DIR / "users.json")))

# حالت اجرا: client (پیش‌فرض) | import | full
APP_MODE = os.getenv("TADAROKAT_MODE", "client").lower()

APP_HOST = os.getenv("TADAROKAT_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("TADAROKAT_PORT", "8000"))

# کلاینت فقط خواندنی از DB مشترک (نوشتن گردش کار در همان DB با WAL)
CLIENT_READ_ONLY = os.getenv("TADAROKAT_CLIENT_READ_ONLY", "0").strip() in ("1", "true", "yes")

# مهاجرت خودکار از اکسل در اولین اجرا
AUTO_MIGRATE = os.getenv("TADAROKAT_AUTO_MIGRATE", "1").strip() in ("1", "true", "yes")

STORAGE_BACKEND = os.getenv("TADAROKAT_STORAGE", "sqlite").lower()  # sqlite | excel

JWT_SECRET = os.getenv("JWT_SECRET", "tadarokat-secret-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12

SHEETS = {
    "purchases": os.getenv("TADAROKAT_PURCHASES_SHEET", "اقلام درخواست خرید"),
}

LOCAL_SHEETS = {
    "purchase_edits": "ویرایش درخواست",
    "issued_inquiries": "استعلام صادر شده",
    "pre_invoices": "پیش فاکتور پیمانکار",
    "pre_invoice_lines": "ردیف پیش فاکتور",
    "product_history": "سابقه خرید کالا",
    "orders": "دستور خرید محلی",
    "deliveries": "تحویل محلی",
    "notifications": "اعلان‌ها",
    "edit_history": "تاریخچه ویرایش",
}

WORKFLOW_TABLES = (
    "purchase_edits",
    "issued_inquiries",
    "pre_invoices",
    "pre_invoice_lines",
    "product_history",
    "orders",
    "deliveries",
    "notifications",
    "edit_history",
)

ROLES = ("admin", "manager", "expert", "warehouse")
MANAGER_ROLES = ("admin", "manager")

PURCHASE_EXPERTS = (
    "فریبا صالح آبادی",
    "مصطفی رضوانی",
    "بهناز عظیمی",
)

PURCHASE_EDITABLE = (
    "وضعیت", "توضیحات", "رمز فوریت", "نوع خرید", "کارشناس خرید", "مهلت استعلام", "شماره استعلام",
)
PURCHASE_EDIT_BLOCKED = frozenset({
    "شماره", "شماره خرید", "purchase_lines", "line_count",
    "has_local_inquiry", "local_inquiry_number", "inquiry_approved", "وضعیت فعلی خرید",
    "updated_at", "updated_by", "overrides_json", "_source",
})