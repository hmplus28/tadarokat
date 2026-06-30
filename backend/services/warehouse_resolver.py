"""تطبیق نام انبار — هر کاربر انبار فقط داده همان انبار را می‌بیند."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from services import local_storage
from services.excel_service import _normalize_id


def normalize_warehouse(name: Optional[str]) -> str:
    text = str(name or "").strip()
    if text.lower() in ("nan", "none", ""):
        return ""
    return text


def warehouses_match(a: Optional[str], b: Optional[str]) -> bool:
    left = normalize_warehouse(a)
    right = normalize_warehouse(b)
    return bool(left and right and left == right)


def _warehouse_from_inquiry_number(inquiry_number: str) -> str:
    inq = str(inquiry_number or "").strip()
    if not inq:
        return ""
    issued = local_storage.get_issued_inquiries()
    if issued.empty or "شماره استعلام" not in issued.columns:
        return ""
    match = issued[issued["شماره استعلام"].astype(str) == inq]
    if match.empty:
        return ""
    return normalize_warehouse(match.iloc[0].get("انبار"))


def _warehouse_from_purchase_number(purchase_number: str) -> str:
    pn = _normalize_id(purchase_number)
    if not pn:
        return ""
    issued = local_storage.get_issued_inquiries()
    if issued.empty or "شماره درخواست خرید" not in issued.columns:
        return ""
    match = issued[issued["شماره درخواست خرید"].map(_normalize_id) == pn]
    if match.empty:
        return ""
    row = match.sort_values("created_at", ascending=False, na_position="last").iloc[0]
    return normalize_warehouse(row.get("انبار"))


def resolve_warehouse_from_order(order: Optional[Dict]) -> str:
    if not isinstance(order, dict):
        return ""
    wh = normalize_warehouse(order.get("انبار"))
    if wh:
        return wh
    wh = _warehouse_from_inquiry_number(str(order.get("شماره استعلام") or ""))
    if wh:
        return wh
    return _warehouse_from_purchase_number(str(order.get("شماره خرید") or ""))


def resolve_warehouse_from_delivery(delivery: Optional[Dict]) -> str:
    if not isinstance(delivery, dict):
        return ""
    wh = normalize_warehouse(delivery.get("انبار"))
    if wh:
        return wh
    order_num = str(delivery.get("شماره دستور") or "").strip()
    if order_num:
        order = local_storage.find_order_by_number(order_num)
        if order:
            return resolve_warehouse_from_order(order)
    return _warehouse_from_purchase_number(str(delivery.get("شماره خرید") or ""))


def list_known_warehouses() -> List[str]:
    names: Set[str] = set()

    from services.user_service import list_users

    for user in list_users():
        wh = normalize_warehouse(user.get("warehouse"))
        if wh:
            names.add(wh)

    for df, col in (
        (local_storage.get_issued_inquiries(), "انبار"),
        (local_storage.get_orders(), "انبار"),
        (local_storage.get_deliveries(), "انبار"),
    ):
        if df is None or df.empty or col not in df.columns:
            continue
        for val in df[col].tolist():
            wh = normalize_warehouse(val)
            if wh:
                names.add(wh)

    return sorted(names)