"""طرح پایگاه داده — metadata، خرید (import)، گردش کار (app)."""

SCHEMA_VERSION = 1

META_DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

IMPORT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    source_file TEXT,
    source_mtime REAL,
    source_sha256 TEXT,
    row_count INTEGER,
    previous_version INTEGER,
    new_version INTEGER,
    message TEXT,
    details_json TEXT
);
"""

PURCHASES_DDL = """
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_number TEXT NOT NULL,
    row_json TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_purchases_number ON purchases(purchase_number);
"""

# جداول گردش کار — ستون‌ها TEXT برای سازگاری با اکسل فارسی
WORKFLOW_DDL = {
    "purchase_edits": """
        CREATE TABLE IF NOT EXISTS purchase_edits (
            شماره TEXT PRIMARY KEY,
            وضعیت TEXT, توضیحات TEXT, "رمز فوریت" TEXT,
            "کارشناس خرید" TEXT, "مهلت استعلام" TEXT, "شماره استعلام" TEXT,
            overrides_json TEXT,
            updated_at TEXT, updated_by TEXT
        );
    """,
    "issued_inquiries": """
        CREATE TABLE IF NOT EXISTS issued_inquiries (
            "شماره استعلام" TEXT PRIMARY KEY,
            "شماره درخواست خرید" TEXT,
            "نوع خرید" TEXT, "تاریخ استعلام" TEXT, وضعیت TEXT,
            "مهلت استعلام" TEXT, "واحد/رمز تامین" TEXT, "رمز فوریت" TEXT,
            "علت خرید" TEXT, انبار TEXT, "درخواست دهنده" TEXT,
            "ریسک عدم خرید" TEXT, "شماره درخواست کالا" TEXT,
            "تاریخ درخواست کالا" TEXT, "تاریخ دریافت" TEXT,
            "صادر کننده سند" TEXT, "کارشناس خرید" TEXT,
            created_at TEXT, created_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_inq_purchase ON issued_inquiries("شماره درخواست خرید");
    """,
    "pre_invoices": """
        CREATE TABLE IF NOT EXISTS pre_invoices (
            id TEXT PRIMARY KEY,
            "شماره استعلام" TEXT,
            "شماره پیش فاکتور" TEXT, "نام پیمانکار" TEXT, "شهر پیمانکار" TEXT,
            "تاریخ پیش فاکتور" TEXT, "نوع فاکتور" TEXT, شرح TEXT,
            "مالیات بر ارزش افزوده" TEXT, "اعمال مالیات ده درصد" TEXT, تخفیف TEXT,
            "زمان تحویل" TEXT, توضیحات TEXT, "جمع کل" TEXT, "انتخاب شده" TEXT,
            "وضعیت مدیر" TEXT, "کامنت مدیر" TEXT, "تاریخ بررسی" TEXT,
            "بررسی کننده" TEXT, created_at TEXT, created_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pi_inquiry ON pre_invoices("شماره استعلام");
    """,
    "pre_invoice_lines": """
        CREATE TABLE IF NOT EXISTS pre_invoice_lines (
            id TEXT PRIMARY KEY,
            preinvoice_id TEXT,
            ردیف TEXT, "عنوان کالا" TEXT, واحد TEXT, فی TEXT, تعداد TEXT,
            "جمع کل" TEXT, توضیحات TEXT, "منتخب مدیر" TEXT,
            "کارشناس ارجاع" TEXT, "شماره دستور" TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pil_preinvoice ON pre_invoice_lines(preinvoice_id);
    """,
    "product_history": """
        CREATE TABLE IF NOT EXISTS product_history (
            id TEXT PRIMARY KEY,
            "کد قلم خریدنی" TEXT, "عنوان کالا" TEXT, فی TEXT, تعداد TEXT, واحد TEXT,
            "نام پیمانکار" TEXT, "شهر پیمانکار" TEXT, "شماره استعلام" TEXT,
            "شماره خرید" TEXT, "تاریخ خرید" TEXT, created_at TEXT, created_by TEXT
        );
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            "شماره دستور" TEXT UNIQUE,
            "شماره استعلام" TEXT, "شماره خرید" TEXT, ردیف TEXT,
            "عنوان کالا" TEXT, واحد TEXT, فی TEXT, تعداد TEXT, انبار TEXT,
            کارشناس TEXT, "نام پیمانکار" TEXT, وضعیت TEXT, "مرحله فعلی" TEXT,
            "تاریخ دستور" TEXT, "شماره سفارش" TEXT, "تاریخ سفارش" TEXT,
            "شماره پرداخت" TEXT, "تاریخ ثبت پرداخت" TEXT, "تاریخ واریز" TEXT,
            "شماره مجوز ورود" TEXT, "تاریخ تحویل" TEXT, "شماره تحویل" TEXT,
            "شماره رسید" TEXT, "تاریخ رسید" TEXT, توضیحات TEXT,
            "صادر کننده" TEXT, created_at TEXT, created_by TEXT, updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_orders_inquiry ON orders("شماره استعلام");
        CREATE INDEX IF NOT EXISTS idx_orders_purchase ON orders("شماره خرید");
    """,
    "deliveries": """
        CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY,
            "شماره تحویل" TEXT,
            "شماره دستور" TEXT, "شماره خرید" TEXT, "عنوان کالا" TEXT,
            انبار TEXT, مقدار TEXT, واحد TEXT, "تاریخ تحویل" TEXT,
            "تحویل گیرنده" TEXT, وضعیت TEXT, توضیحات TEXT,
            created_at TEXT, created_by TEXT, updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_del_order ON deliveries("شماره دستور");
    """,
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            username TEXT, warehouse TEXT, عنوان TEXT, پیام TEXT,
            نوع TEXT, مرجع TEXT, "خوانده شده" TEXT, created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(username);
    """,
    "edit_history": """
        CREATE TABLE IF NOT EXISTS edit_history (
            id TEXT PRIMARY KEY,
            "نوع موجودیت" TEXT, شناسه TEXT, عملیات TEXT, فیلد TEXT,
            "مقدار قبلی" TEXT, "مقدار جدید" TEXT, کاربر TEXT, created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_hist_entity ON edit_history("نوع موجودیت", شناسه);
    """,
}


USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    expert TEXT,
    warehouse TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
"""

CATEGORIES_DDL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT
);
"""

GOODS_CATEGORIES = [
    "ایمنی و بهداشت",
    "اقلام مصرفی",
    "آی تی",
    "ابنیه و مصالح",
    "نت و تاسیسات",
    "عمومی تولید",
    "چاپ و تبلیغات",
]


def all_ddl() -> list:
    parts = [META_DDL, IMPORT_LOG_DDL, PURCHASES_DDL, USERS_DDL, CATEGORIES_DDL]
    parts.extend(WORKFLOW_DDL.values())
    return parts


def seed_categories(conn) -> None:
    import datetime
    import sqlite3  # for type checkers only if needed
    now = datetime.datetime.utcnow().isoformat()
    for name in GOODS_CATEGORIES:
        conn.execute(
            "INSERT OR IGNORE INTO categories(name, created_at) VALUES (?, ?)",
            (name, now),
        )
