"""تولید output.xlsx از پایگاه داده — نه منبع حقیقت."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from config import OUTPUT_EXCEL_PATH, WORKFLOW_TABLES
from db.connection import get_db_manager


def _rows_to_df(conn, table: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
    except Exception:
        return pd.DataFrame()


def export_purchases_df() -> pd.DataFrame:
    mgr = get_db_manager()
    with mgr.connect(write=False) as conn:
        rows = conn.execute("SELECT row_json FROM purchases ORDER BY id").fetchall()
    if not rows:
        return pd.DataFrame()
    records: List[Dict[str, Any]] = []
    for r in rows:
        try:
            records.append(json.loads(r["row_json"]))
        except json.JSONDecodeError:
            continue
    return pd.DataFrame(records)


def export_to_excel(output_path: Optional[Path] = None) -> Path:
    out = Path(output_path or OUTPUT_EXCEL_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    mgr = get_db_manager()

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        purchases = export_purchases_df()
        purchases.to_excel(writer, sheet_name="درخواست‌های خرید", index=False)

        with mgr.connect(write=False) as conn:
            sheet_names = {
                "purchase_edits": "ویرایش درخواست",
                "issued_inquiries": "استعلام صادر شده",
                "pre_invoices": "پیش فاکتور",
                "pre_invoice_lines": "ردیف پیش فاکتور",
                "orders": "دستور خرید",
                "deliveries": "تحویل",
                "product_history": "سابقه خرید",
                "notifications": "اعلان‌ها",
                "edit_history": "تاریخچه",
            }
            for table in WORKFLOW_TABLES:
                df = _rows_to_df(conn, table)
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_names.get(table, table)[:31], index=False)

        meta_rows = []
        with mgr.connect(write=False) as conn:
            for row in conn.execute("SELECT key, value, updated_at FROM meta ORDER BY key"):
                meta_rows.append(dict(row))
        if meta_rows:
            pd.DataFrame(meta_rows).to_excel(writer, sheet_name="metadata", index=False)

    from datetime import datetime
    with mgr.connect(write=True) as conn:
        mgr._set_meta(conn, "last_export_at", datetime.utcnow().isoformat())

    return out