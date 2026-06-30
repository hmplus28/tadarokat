"""ویرایش کامل موجودیت‌های ذخیره‌شده — فقط مدیر سیستم."""

from typing import Any, Dict, Optional

from services import history_service, local_storage
from services.excel_service import invalidate_cache
from services.json_util import json_safe

ENTITY_META: Dict[str, Dict[str, Any]] = {
    "inquiry": {
        "sheet": "issued_inquiries",
        "id_col": "شماره استعلام",
        "label": "استعلام",
        "blocked": frozenset({"created_at", "created_by"}),
    },
    "pre_invoice": {
        "sheet": "pre_invoices",
        "id_col": "id",
        "label": "پیش‌فاکتور",
        "blocked": frozenset({"id", "created_at", "created_by"}),
    },
    "pre_invoice_line": {
        "sheet": "pre_invoice_lines",
        "id_col": "id",
        "label": "ردیف پیش‌فاکتور",
        "blocked": frozenset({"id", "preinvoice_id"}),
    },
    "order": {
        "sheet": "orders",
        "id_col": "id",
        "label": "دستور خرید",
        "blocked": frozenset({"id", "created_at", "created_by"}),
    },
    "delivery": {
        "sheet": "deliveries",
        "id_col": "id",
        "label": "تحویل",
        "blocked": frozenset({"id", "created_at", "created_by"}),
    },
}


def _read_entity_df(entity_type: str):
    meta = ENTITY_META.get(entity_type)
    if not meta:
        raise ValueError("نوع موجودیت نامعتبر است")
    readers = {
        "issued_inquiries": local_storage.get_issued_inquiries,
        "pre_invoices": local_storage.get_pre_invoices,
        "pre_invoice_lines": local_storage.get_pre_invoice_lines,
        "orders": local_storage.get_orders,
        "deliveries": local_storage.get_deliveries,
    }
    return meta, readers[meta["sheet"]]()


def get_entity(entity_type: str, entity_id: str) -> Optional[Dict]:
    meta, df = _read_entity_df(entity_type)
    if df.empty or meta["id_col"] not in df.columns:
        return None
    match = df[df[meta["id_col"]].astype(str) == str(entity_id)]
    if match.empty:
        return None
    return json_safe(match.iloc[0].to_dict())


def update_entity(entity_type: str, entity_id: str, updates: Dict[str, Any], username: str) -> Dict:
    meta, df = _read_entity_df(entity_type)
    id_col = meta["id_col"]
    blocked = meta["blocked"]
    if df.empty or id_col not in df.columns:
        raise ValueError("داده‌ای یافت نشد")

    allowed = {
        k: v for k, v in updates.items()
        if k not in blocked and k in df.columns
    }
    if not allowed:
        raise ValueError("فیلد مجاز برای ویرایش یافت نشد")

    mask = df[id_col].astype(str) == str(entity_id)
    if not mask.any():
        raise ValueError("رکورد یافت نشد")

    before = df[mask].iloc[0].to_dict()
    idx = df[mask].index[0]
    for k, v in allowed.items():
        if df[k].dtype != object:
            df[k] = df[k].astype(object)
        df.loc[idx, k] = v

    if entity_type in ("order", "delivery"):
        from datetime import datetime
        if "updated_at" in df.columns:
            df.loc[idx, "updated_at"] = datetime.utcnow().isoformat()

    local_storage._write_sheet(meta["sheet"], df)

    entity_label = meta["label"]
    hist_id = str(before.get(id_col) or entity_id)
    if entity_type == "order" and before.get("شماره دستور"):
        hist_id = str(before["شماره دستور"])
    elif entity_type == "delivery" and before.get("شماره تحویل"):
        hist_id = str(before["شماره تحویل"])

    history_service.log_field_changes(entity_label, hist_id, username, allowed, before)
    invalidate_cache()
    return json_safe(df[mask].iloc[0].to_dict())