"""مهاجرت یک‌باره از اکسل به SQLite."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from config import (
    APP_MODE,
    AUTO_MIGRATE,
    DB_CURRENT_PATH,
    EXCEL_PATH,
    INPUT_EXCEL_PATH,
    LOCAL_EXCEL_PATH,
    SHEETS,
    STORAGE_BACKEND,
    WORKFLOW_TABLES,
)
from db.connection import DatabaseManager, get_db_manager
from db.import_service import ImportService, _normalize_col, _normalize_purchase_number

logger = logging.getLogger("tadarokat.migrate")

# نگاشت sheet_key → نام جدول SQLite
SHEET_TABLE_MAP = {k: k for k in WORKFLOW_TABLES}


def _read_legacy_local_sheet(sheet_key: str) -> pd.DataFrame:
    from services.local_storage import LOCAL_SHEETS, SHEET_HEADERS, _align_dataframe

    if not LOCAL_EXCEL_PATH.exists():
        return pd.DataFrame()
    sheet_name = LOCAL_SHEETS[sheet_key]
    headers = SHEET_HEADERS[sheet_key]
    try:
        df = pd.read_excel(LOCAL_EXCEL_PATH, sheet_name=sheet_name, engine="openpyxl")
        return _align_dataframe(df, headers)
    except Exception:
        return pd.DataFrame(columns=headers)


def migrate_workflow_from_excel(conn) -> Dict[str, int]:
    counts = {}
    mgr = DatabaseManager(DB_CURRENT_PATH)
    for sheet_key in WORKFLOW_TABLES:
        df = _read_legacy_local_sheet(sheet_key)
        table = SHEET_TABLE_MAP[sheet_key]
        conn.execute(f'DELETE FROM "{table}"')
        if df.empty:
            counts[table] = 0
            continue
        df = df.where(pd.notna(df), None)
        cols = list(df.columns)
        col_sql = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        conn.executemany(
            f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})',
            [tuple(row[c] for c in cols) for _, row in df.iterrows()],
        )
        counts[table] = len(df)
    mgr._set_meta(conn, "migrated_from_local_excel", datetime.utcnow().isoformat())
    return counts


def migrate_purchases_from_excel(conn, excel_path: Path) -> int:
    sheet = SHEETS["purchases"]
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet, engine="openpyxl")
    except Exception:
        xl = pd.ExcelFile(excel_path, engine="openpyxl")
        df = pd.read_excel(excel_path, sheet_name=xl.sheet_names[0], engine="openpyxl") if xl.sheet_names else pd.DataFrame()
    if df.empty:
        return 0
    df.columns = [_normalize_col(c) for c in df.columns]
    conn.execute("DELETE FROM purchases")
    imported_at = datetime.utcnow().isoformat()
    rows = []
    for rec in df.to_dict(orient="records"):
        num = _normalize_purchase_number(rec.get("شماره"))
        if not num:
            continue
        clean = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
        rows.append((num, json.dumps(clean, ensure_ascii=False, default=str), imported_at))
    conn.executemany(
        "INSERT INTO purchases(purchase_number, row_json, imported_at) VALUES (?, ?, ?)",
        rows,
    )
    return len(rows)


def _ensure_purchase_edits_columns(conn) -> None:
    cols = {row[1] for row in conn.execute('PRAGMA table_info("purchase_edits")').fetchall()}
    if "overrides_json" not in cols:
        conn.execute('ALTER TABLE purchase_edits ADD COLUMN overrides_json TEXT')


def _ensure_workflow_columns(conn) -> None:
    from config import WORKFLOW_TABLES
    from services.local_storage import SHEET_HEADERS

    for table in WORKFLOW_TABLES:
        headers = SHEET_HEADERS.get(table, [])
        if not headers:
            continue
        try:
            existing = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
        except Exception:
            continue
        for col in headers:
            if col not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT')


def ensure_database_ready() -> dict:
    """ایجاد DB در صورت نبود + مهاجرت از اکسل."""
    if STORAGE_BACKEND != "sqlite":
        return {"backend": "excel", "skipped": True}

    mgr = get_db_manager()
    created = not DB_CURRENT_PATH.exists()

    with mgr.connect(write=True) as conn:
        mgr.initialize_schema(conn)
        _ensure_purchase_edits_columns(conn)
        _ensure_workflow_columns(conn)
        if created or mgr.get_meta(conn, "migrated_from_local_excel") is None:
            if LOCAL_EXCEL_PATH.exists():
                wf = migrate_workflow_from_excel(conn)
                logger.info("Workflow migrated: %s", wf)
            excel_src = INPUT_EXCEL_PATH if INPUT_EXCEL_PATH.exists() else EXCEL_PATH
            # Only migrate purchases if we have no purchases yet (avoid destroying fresh import data)
            purchase_count = 0
            try:
                purchase_count = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
            except Exception:
                pass
            if excel_src.exists() and purchase_count == 0:
                cnt = migrate_purchases_from_excel(conn, excel_src)
                mgr._set_meta(conn, "last_import_at", datetime.utcnow().isoformat())
                mgr._set_meta(conn, "last_import_rows", str(cnt))
                logger.info("Purchases migrated: %d rows", cnt)
            mgr.bump_version(conn)

    return {"backend": "sqlite", "created": created, "path": str(DB_CURRENT_PATH)}


def _ensure_schema_only() -> dict:
    mgr = get_db_manager()
    with mgr.connect(write=True) as conn:
        mgr.initialize_schema(conn)
        _ensure_purchase_edits_columns(conn)
        _ensure_workflow_columns(conn)
    return {"backend": "sqlite", "client": True, "path": str(DB_CURRENT_PATH)}


def run_if_needed() -> dict:
    if STORAGE_BACKEND != "sqlite":
        return {"skipped": True, "reason": "not_sqlite"}

    if APP_MODE == "client":
        if not DB_CURRENT_PATH.exists():
            return {
                "skipped": True,
                "reason": "client_no_db",
                "path": str(DB_CURRENT_PATH),
                "hint": "پایگاه share هنوز ساخته نشده — scripts/init_share را یک بار اجرا کنید.",
            }
        return _ensure_schema_only()

    if not AUTO_MIGRATE:
        return {"skipped": True, "reason": "auto_migrate_off"}
    if DB_CURRENT_PATH.exists():
        mgr = get_db_manager()
        with mgr.connect(write=False) as conn:
            if mgr.get_meta(conn, "migrated_from_local_excel"):
                return {"skipped": True, "reason": "already_migrated"}
    return ensure_database_ready()