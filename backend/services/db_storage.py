"""دسترسی SQLite به جداول گردش کار — جایگزین شیت‌های local_changes.xlsx."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from config import STORAGE_BACKEND, WORKFLOW_TABLES
from db.connection import ReadOnlyClientError, get_db_manager

# re-export headers from local_storage for سازگاری
from services.local_storage import (  # noqa: F401
    DELIVERY_HEADERS,
    EDIT_HISTORY_HEADERS,
    INQUIRY_HEADERS,
    LINE_HEADERS,
    NOTIFICATION_HEADERS,
    ORDER_HEADERS,
    PREINVOICE_HEADERS,
    PRODUCT_HISTORY_HEADERS,
    PURCHASE_EDIT_HEADERS,
    SHEET_HEADERS,
)


def _enabled() -> bool:
    return STORAGE_BACKEND == "sqlite"


def _table_for_sheet(sheet_key: str) -> str:
    if sheet_key not in WORKFLOW_TABLES:
        raise KeyError(sheet_key)
    return sheet_key


def ensure_database() -> None:
    from db.migrate_legacy import ensure_database_ready
    ensure_database_ready()


def read_sheet(sheet_key: str) -> pd.DataFrame:
    headers = SHEET_HEADERS[sheet_key]
    if not _enabled():
        raise RuntimeError("db_storage only in sqlite mode")
    ensure_database()
    table = _table_for_sheet(sheet_key)
    mgr = get_db_manager()
    with mgr.connect(write=False) as conn:
        try:
            df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
        except Exception:
            df = pd.DataFrame(columns=headers)
    if df.empty:
        return pd.DataFrame(columns=headers)
    for col in headers:
        if col not in df.columns:
            df[col] = None
    return df[headers]


def write_sheet(sheet_key: str, df: pd.DataFrame) -> None:
    if not _enabled():
        raise RuntimeError("db_storage only in sqlite mode")
    ensure_database()
    table = _table_for_sheet(sheet_key)
    headers = SHEET_HEADERS[sheet_key]
    out = df.copy()
    for col in headers:
        if col not in out.columns:
            out[col] = None
    out = out[headers].where(pd.notna(out[headers]), None)

    mgr = get_db_manager()
    try:
        with mgr.connect(write=True) as conn:
            conn.execute(f'DELETE FROM "{table}"')
            if out.empty:
                mgr.bump_version(conn)
                return
            cols = headers
            col_sql = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join("?" for _ in cols)
            conn.executemany(
                f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})',
                [tuple(row[c] for c in cols) for _, row in out.iterrows()],
            )
            mgr.bump_version(conn)
    except ReadOnlyClientError as exc:
        raise PermissionError(str(exc)) from exc


def db_info() -> dict:
    if not _enabled():
        return {"backend": "excel"}
    mgr = get_db_manager()
    info = mgr.db_info()
    info["backend"] = "sqlite"
    with mgr.connect(write=False) as conn:
        for table in WORKFLOW_TABLES:
            try:
                info[f"count_{table}"] = conn.execute(f'SELECT COUNT(*) c FROM "{table}"').fetchone()["c"]
            except Exception:
                info[f"count_{table}"] = 0
    return info


def new_id() -> str:
    return str(uuid.uuid4())[:12]


def utc_now() -> str:
    return datetime.utcnow().isoformat()