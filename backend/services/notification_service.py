from typing import Dict, List, Optional, Set

from services import local_storage
from services.order_stages import is_delivery_completed
from services.warehouse_resolver import (
    normalize_warehouse,
    resolve_warehouse_from_delivery,
    resolve_warehouse_from_order,
    warehouses_match,
)


def notify_warehouse_delivery(
    warehouse: str,
    title: str,
    message: str,
    ref_id: str,
) -> None:
    """اعلان تحویل کامل — فقط وقتی مجوز ورود و تاریخ تحویل ثبت شده باشد."""
    notify_warehouse(warehouse, title, message, "delivery_completed", ref_id)


def notify_warehouse(warehouse: str, title: str, message: str, ref_type: str, ref_id: str) -> None:
    wh = normalize_warehouse(warehouse)
    if not wh:
        return
    from services.user_service import list_users

    for user in list_users():
        if user.get("role") != "warehouse" or not user.get("active", True):
            continue
        user_wh = normalize_warehouse(user.get("warehouse"))
        if warehouses_match(user_wh, wh):
            local_storage.append_notification({
                "username": user["username"],
                "warehouse": wh,
                "عنوان": title,
                "پیام": message,
                "نوع": ref_type,
                "مرجع": ref_id,
            })


def _is_delivery_notification(item: Dict) -> bool:
    ref_type = str(item.get("نوع") or "").lower()
    if ref_type in ("delivery_completed", "delivery"):
        return True
    title = str(item.get("عنوان") or "")
    return title in ("تحویل شده", "ثبت تحویل")


def _delivery_completion_record(delivery: Dict, order: Optional[Dict] = None) -> Dict:
    record = dict(order or delivery or {})
    if order:
        record.update({k: v for k, v in order.items() if v not in (None, "", "nan")})
    if delivery:
        if not str(record.get("تاریخ تحویل") or "").strip():
            record["تاریخ تحویل"] = delivery.get("تاریخ تحویل")
        if not str(record.get("شماره مجوز ورود") or "").strip():
            record["شماره مجوز ورود"] = delivery.get("شماره مجوز ورود") or delivery.get("شماره تحویل")
    return record


def _existing_delivery_refs(username: str) -> Set[str]:
    refs: Set[str] = set()
    for item in local_storage.get_notifications(username=username):
        if not _is_delivery_notification(item):
            continue
        ref = str(item.get("مرجع") or "").strip()
        if ref:
            refs.add(ref)
    return refs


def sync_warehouse_delivery_notifications(username: str, warehouse: str) -> int:
    """اعلان‌های تحویل کامل گذشته را برای کاربر انبار همگام می‌کند."""
    wh = normalize_warehouse(warehouse)
    if not wh or not username:
        return 0

    existing_refs = _existing_delivery_refs(username)
    created = 0

    deliveries_df = local_storage.get_deliveries()
    if deliveries_df.empty:
        return 0

    for _, row in deliveries_df.iterrows():
        delivery = row.to_dict()
        delivery_wh = resolve_warehouse_from_delivery(delivery)
        if not warehouses_match(delivery_wh, wh):
            continue

        order = None
        order_num = str(delivery.get("شماره دستور") or "").strip()
        if order_num:
            order = local_storage.find_order_by_number(order_num)

        record = _delivery_completion_record(delivery, order)
        if not is_delivery_completed(record):
            continue

        ref_id = str(delivery.get("id") or delivery.get("شماره تحویل") or "").strip()
        if not ref_id or ref_id in existing_refs:
            continue

        delivery_number = str(delivery.get("شماره تحویل") or ref_id)
        product = str(delivery.get("عنوان کالا") or (order or {}).get("عنوان کالا") or "")
        order_num = order_num or str((order or {}).get("شماره دستور") or "")
        message = f"تحویل {delivery_number}"
        if product:
            message += f" — {product}"
        if order_num:
            message += f" — دستور {order_num}"

        local_storage.append_notification({
            "username": username,
            "warehouse": wh,
            "عنوان": "تحویل شده",
            "پیام": message,
            "نوع": "delivery_completed",
            "مرجع": ref_id,
        })
        existing_refs.add(ref_id)
        created += 1

    orders_df = local_storage.get_orders()
    if not orders_df.empty:
        for _, row in orders_df.iterrows():
            order = row.to_dict()
            order_wh = resolve_warehouse_from_order(order)
            if not warehouses_match(order_wh, wh):
                continue
            if not is_delivery_completed(order):
                continue
            ref_id = str(order.get("id") or order.get("شماره دستور") or "").strip()
            if not ref_id or ref_id in existing_refs:
                continue
            order_num = str(order.get("شماره دستور") or ref_id)
            product = str(order.get("عنوان کالا") or "")
            local_storage.append_notification({
                "username": username,
                "warehouse": wh,
                "عنوان": "تحویل شده",
                "پیام": f"خرید {order_num}" + (f" — {product}" if product else "") + " — مجوز و تاریخ ثبت شد",
                "نوع": "delivery_completed",
                "مرجع": ref_id,
            })
            existing_refs.add(ref_id)
            created += 1

    return created


def _coerce_read_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in ("true", "1", "yes")


def _normalize_notification(item: Dict) -> Dict:
    row = dict(item)
    row["خوانده شده"] = _coerce_read_flag(row.get("خوانده شده"))
    return row


def list_for_user(
    username: str,
    unread_only: bool = False,
    *,
    delivery_only: bool = False,
    warehouse: Optional[str] = None,
) -> List[Dict]:
    if delivery_only and warehouse:
        sync_warehouse_delivery_notifications(username, warehouse)

    items = local_storage.get_notifications(username=username, unread_only=unread_only)
    if delivery_only:
        wh = normalize_warehouse(warehouse)
        filtered = []
        for item in items:
            if not _is_delivery_notification(item):
                continue
            item_wh = normalize_warehouse(item.get("warehouse"))
            if wh and item_wh and not warehouses_match(item_wh, wh):
                continue
            filtered.append(item)
        items = filtered
    return [_normalize_notification(item) for item in items]


def mark_read(notification_id: str, username: str) -> Optional[Dict]:
    result = local_storage.mark_notification_read(notification_id, username)
    return _normalize_notification(result) if result else None


def mark_all_read(username: str, *, warehouse: Optional[str] = None, delivery_only: bool = False) -> int:
    items = list_for_user(
        username,
        delivery_only=delivery_only,
        warehouse=warehouse,
    )
    count = 0
    for item in items:
        if item.get("خوانده شده"):
            continue
        nid = str(item.get("id") or "").strip()
        if nid and mark_read(nid, username):
            count += 1
    return count