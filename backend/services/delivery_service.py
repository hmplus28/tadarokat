from datetime import datetime
from typing import Dict, Optional

from services import local_storage, notification_service
from services.excel_service import invalidate_cache
from services.order_stages import is_delivery_completed
from services.notification_service import _delivery_completion_record
from services.warehouse_resolver import resolve_warehouse_from_delivery


def _maybe_notify_warehouse_delivery(delivery: dict) -> None:
    """اعلان انبار فقط برای تحویل کامل (مجوز ورود + تاریخ تحویل)."""
    order_num = str(delivery.get("شماره دستور") or "").strip()
    order = local_storage.find_order_by_number(order_num) if order_num else None
    record = _delivery_completion_record(delivery, order)
    if not is_delivery_completed(record):
        return
    warehouse = resolve_warehouse_from_delivery(delivery)
    delivery_number = str(delivery.get("شماره تحویل") or delivery.get("id") or "")
    product = str(delivery.get("عنوان کالا") or (order or {}).get("عنوان کالا") or "")
    notification_service.notify_warehouse_delivery(
        warehouse,
        "تحویل شده",
        f"تحویل {delivery_number} — {product} — مجوز و تاریخ ثبت شد",
        str(delivery.get("id", delivery_number)),
    )


def _today() -> str:
    try:
        import jdatetime
        return jdatetime.date.today().strftime("%Y/%m/%d")
    except ImportError:
        return datetime.now().strftime("%Y/%m/%d")


def create_delivery(payload: Dict, username: str, *, notify: bool = True) -> Dict:
    delivery_number = str(payload.get("شماره تحویل") or payload.get("delivery_number") or "").strip()
    if not delivery_number:
        raise ValueError("شماره تحویل الزامی است")
    if local_storage.delivery_number_exists(delivery_number):
        raise ValueError("شماره تحویل تکراری است")

    record = {
        "شماره تحویل": delivery_number,
        "شماره دستور": payload.get("شماره دستور"),
        "شماره خرید": payload.get("شماره خرید"),
        "عنوان کالا": payload.get("عنوان کالا"),
        "انبار": payload.get("انبار"),
        "مقدار": payload.get("مقدار"),
        "واحد": payload.get("واحد"),
        "تاریخ تحویل": payload.get("تاریخ تحویل") or _today(),
        "تحویل گیرنده": payload.get("تحویل گیرنده"),
        "وضعیت": payload.get("وضعیت") or "ثبت شده",
        "توضیحات": payload.get("توضیحات") or "",
    }
    saved = local_storage.append_delivery(record, username)
    from services import history_service
    history_service.log_action("تحویل", delivery_number, username, "ایجاد", str(record.get("عنوان کالا") or ""))
    if notify:
        _maybe_notify_warehouse_delivery(saved)
    invalidate_cache()
    return {"ok": True, "delivery": saved}


def list_deliveries(
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    user: Optional[dict] = None,
    page_cap: int = 200,
) -> Dict:
    from services.order_service import sync_deliveries_for_completed_orders

    sync_username = (user or {}).get("username") or "system"
    sync_deliveries_for_completed_orders(sync_username)

    df = local_storage.get_deliveries()
    if not df.empty and "created_at" in df.columns:
        df = df.sort_values("created_at", ascending=False, na_position="last")
    if user and user.get("role") == "warehouse" and user.get("warehouse"):
        from services.warehouse_resolver import normalize_warehouse, resolve_warehouse_from_delivery, warehouses_match

        user_wh = normalize_warehouse(user.get("warehouse"))

        def _belongs(row) -> bool:
            rec = row.to_dict() if hasattr(row, "to_dict") else dict(row)
            return warehouses_match(resolve_warehouse_from_delivery(rec), user_wh)

        if not df.empty:
            df = df[df.apply(_belongs, axis=1)]
    elif user and user.get("role") == "expert" and not df.empty:
        from services.access_service import delivery_visible_for_user

        df = df[df.apply(lambda r: delivery_visible_for_user(r.to_dict(), user), axis=1)]
    result = local_storage.paginate_df(
        df, page, page_size, search,
        ["شماره تحویل", "شماره دستور", "شماره خرید", "عنوان کالا", "انبار", "تحویل گیرنده"],
        page_cap=page_cap,
    )
    for item in result.get("items") or []:
        order_num = str(item.get("شماره دستور") or "").strip()
        if order_num:
            order = local_storage.find_order_by_number(order_num)
            if order:
                item["order_id"] = order.get("id")
                item["order_stage"] = order.get("مرحله فعلی")
    result["source"] = "local"
    return result


def update_delivery(delivery_id: str, payload: Dict, username: str, *, notify: bool = True) -> Dict:
    from services import history_service

    allowed = {"وضعیت", "مقدار", "واحد", "تاریخ تحویل", "تحویل گیرنده", "توضیحات"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise ValueError("فیلد مجاز یافت نشد")
    deliveries_df = local_storage.get_deliveries()
    before = None
    if not deliveries_df.empty:
        match = deliveries_df[deliveries_df["id"].astype(str) == str(delivery_id)]
        if not match.empty:
            before = match.iloc[0].to_dict()
    result = local_storage.update_delivery(delivery_id, updates, username)
    if before:
        entity_id = str(before.get("شماره تحویل") or delivery_id)
        history_service.log_field_changes("تحویل", entity_id, username, updates, before)
    if not result:
        raise ValueError("تحویل یافت نشد")
    if notify:
        _maybe_notify_warehouse_delivery(result)
    invalidate_cache()
    return {"ok": True, "delivery": result}