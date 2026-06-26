import os
from pathlib import Path

from local_config import apply_share_config, CONFIG_FILE, default_local_data_dir

apply_share_config()

BASE_DIR = Path(__file__).resolve().parent.parent

# مسیر داده مشترک — از share.config.json یا TADAROKAT_SHARED_DATA
# مثال شبکه: /mnt/share/tadarokat/data یا //server/share/tadarokat/data
SHARED_DATA_DIR = Path(os.getenv("TADAROKAT_SHARED_DATA", str(BASE_DIR / "data"))).resolve()

# داده محلی هر کلاینت — users.json و تنظیمات (جدا از share)
LOCAL_DATA_DIR = Path(
    os.getenv("TADAROKAT_LOCAL_DATA", str(default_local_data_dir()))
).resolve()

DATA_DIR = SHARED_DATA_DIR
FRONTEND_DIR = BASE_DIR / "frontend"

# ── فایل‌های منبع (اکسل روزانه — فقط Import Service می‌خواند) ──
INPUT_EXCEL_PATH = Path(os.getenv("TADAROKAT_INPUT_EXCEL", str(DATA_DIR / "input.xlsx")))
# سازگاری با مسیر قبلی
SOURCE_EXCEL_PATH = Path(os.getenv("TADAROKAT_SOURCE_EXCEL", str(DATA_DIR / "purchases.xlsx")))
EXCEL_PATH = INPUT_EXCEL_PATH if INPUT_EXCEL_PATH.exists() else SOURCE_EXCEL_PATH

OUTPUT_EXCEL_PATH = Path(os.getenv("TADAROKAT_OUTPUT_EXCEL", str(DATA_DIR / "output.xlsx")))

# ── پایگاه داده مشترک ──
DB_CURRENT_PATH = Path(os.getenv("TADAROKAT_DB_CURRENT", str(DATA_DIR / "db_current.db")))
DB_NEW_PATH = Path(os.getenv("TADAROKAT_DB_NEW", str(DATA_DIR / "db_new.db")))
DB_OLD_PATH = Path(os.getenv("TADAROKAT_DB_OLD", str(DATA_DIR / "db_old.db")))
LOCK_FLAG_PATH = Path(os.getenv("TADAROKAT_LOCK_FLAG", str(DATA_DIR / "lock.flag")))
LOGS_DIR = Path(os.getenv("TADAROKAT_LOGS_DIR", str(DATA_DIR / "logs")))

# اکسل محلی قدیمی — فقط برای مهاجرت یک‌باره
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