from datetime import datetime
from typing import Any, Dict, List, Optional

from services import local_storage, notification_service
from services.inquiry_service import get_inquiry_detail
from services.excel_service import invalidate_cache
from services.json_util import json_safe
from services.order_stages import (
    STAGE_REQUIRED_FIELDS,
    is_delivery_completed,
    is_stage_completed,
    is_workflow_complete,
    locked_fields_for,
    next_stage_to_complete,
    normalize_stage,
    order_is_delivered,
    stage_index,
    workflow_meta,
)


def _now_jalali() -> str:
    try:
        import jdatetime
        return jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M")
    except ImportError:
        return datetime.now().strftime("%Y/%m/%d %H:%M")


def _today_jalali() -> str:
    try:
        import jdatetime
        return jdatetime.date.today().strftime("%Y/%m/%d")
    except ImportError:
        return datetime.now().strftime("%Y/%m/%d")


def issue_order(payload: Dict, manager_name: str, username: str) -> Dict:
    order_number = str(payload.get("شماره دستور") or payload.get("order_number") or "").strip()
    inquiry_number = str(payload.get("شماره استعلام") or "").strip()
    preinvoice_id = str(payload.get("preinvoice_id") or "").strip()
    line_id = str(payload.get("line_id") or "").strip()

    if not order_number:
        raise ValueError("شماره دستور الزامی است")
    if not inquiry_number:
        raise ValueError("شماره استعلام الزامی است")

    inquiry = get_inquiry_detail(inquiry_number)
    if not inquiry:
        raise ValueError("استعلام یافت نشد")

    purchase_number = str(inquiry.get("شماره درخواست خرید") or "")
    warehouse = str(inquiry.get("انبار") or "")
    expert = str(payload.get("کارشناس") or inquiry.get("کارشناس خرید") or inquiry.get("صادر کننده سند") or "").strip()

    contractor = str(payload.get("نام پیمانکار") or "")
    product_title = payload.get("عنوان کالا") or ""
    row_num = payload.get("ردیف")
    unit = payload.get("واحد")
    price = payload.get("فی")
    qty = payload.get("تعداد")

    if preinvoice_id:
        pre_df = local_storage.get_pre_invoices()
        if not pre_df.empty:
            match = pre_df[pre_df["id"].astype(str) == preinvoice_id]
            if not match.empty:
                contractor = contractor or str(match.iloc[0].get("نام پیمانکار") or "")

    if line_id:
        lines_df = local_storage.get_pre_invoice_lines()
        if not lines_df.empty:
            lm = lines_df[lines_df["id"].astype(str) == line_id]
            if not lm.empty:
                line = lm.iloc[0]
                product_title = product_title or line.get("عنوان کالا")
                row_num = row_num if row_num is not None else line.get("ردیف")
                unit = unit or line.get("واحد")
                price = price if price is not None else line.get("فی")
                qty = qty if qty is not None else line.get("تعداد")

    if local_storage.order_number_exists(order_number):
        raise ValueError("شماره دستور تکراری است")

    order_date = _now_jalali()

    record = {
        "شماره دستور": order_number,
        "شماره استعلام": inquiry_number,
        "شماره خرید": purchase_number,
        "ردیف": row_num,
        "عنوان کالا": product_title,
        "واحد": unit,
        "فی": price,
        "تعداد": qty,
        "انبار": warehouse,
        "کارشناس": expert,
        "نام پیمانکار": contractor,
        "وضعیت": "صدور دستور",
        "مرحله فعلی": "دستور خرید",
        "تاریخ دستور": order_date,
        "تاریخ سفارش": None,
        "تاریخ تحویل": None,
        "تاریخ رسید": None,
        "توضیحات": payload.get("توضیحات") or "",
        "صادر کننده": manager_name,
    }
    saved = local_storage.append_order(record, username)
    from services import history_service
    history_service.log_action(
        "دستور خرید",
        order_number,
        username,
        "ایجاد",
        f"استعلام {inquiry_number} · {product_title or '—'} · کارشناس {expert}",
    )

    invalidate_cache()
    return {"ok": True, "order": saved}


def list_orders(
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    user: Optional[dict] = None,
    exclude_completed: bool = True,
    page_cap: int = 200,
) -> Dict:
    df = local_storage.get_orders()
    if exclude_completed and not df.empty and "مرحله فعلی" in df.columns:
        df = df[~df.apply(lambda r: order_is_delivered(r.to_dict()), axis=1)]
    if user:
        role = user.get("role")
        if role == "expert":
            expert_name = user.get("expert") or user.get("name") or ""
            if expert_name and "کارشناس" in df.columns:
                df = df[df["کارشناس"].astype(str).str.contains(expert_name, na=False)]
        elif role == "warehouse" and user.get("warehouse"):
            from services.warehouse_resolver import resolve_warehouse_from_order, warehouses_match

            user_wh = str(user.get("warehouse") or "")
            if not df.empty:
                df = df[df.apply(lambda r: warehouses_match(resolve_warehouse_from_order(r.to_dict()), user_wh), axis=1)]
    if not df.empty and "created_at" in df.columns:
        df = df.sort_values("created_at", ascending=False, na_position="last")
    result = local_storage.paginate_df(
        df, page, page_size, search,
        ["شماره دستور", "شماره استعلام", "شماره خرید", "عنوان کالا", "کارشناس", "انبار", "نام پیمانکار"],
        page_cap=page_cap,
    )
    result["items"] = [json_safe(item) for item in result.get("items") or []]
    result["source"] = "local"
    return json_safe(result)


def _get_order_row(order_id: str) -> Optional[Dict]:
    orders_df = local_storage.get_orders()
    if orders_df.empty:
        return None
    match = orders_df[orders_df["id"].astype(str) == str(order_id)]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def _migrate_legacy_order_fields(order: Dict) -> Dict:
    row = dict(order)
    stage = normalize_stage(row.get("مرحله فعلی"))
    row["مرحله فعلی"] = stage
    if not row.get("شماره مجوز ورود") and row.get("شماره تحویل"):
        row["شماره مجوز ورود"] = row.get("شماره تحویل")
    return row


def _synthesize_order_from_delivery(delivery: Dict) -> Dict:
    """وقتی فقط تحویل import شده و رکورد دستور در سیستم نیست."""
    order_num = str(delivery.get("شماره دستور") or "").strip()
    delivery_num = str(delivery.get("شماره تحویل") or "").strip()
    status = str(delivery.get("وضعیت") or "")
    stage = "تحویل" if "تحویل" in status else "دستور خرید"
    return {
        "id": f"delivery:{delivery.get('id')}",
        "شماره دستور": order_num,
        "شماره خرید": delivery.get("شماره خرید"),
        "عنوان کالا": delivery.get("عنوان کالا"),
        "انبار": delivery.get("انبار"),
        "تعداد": delivery.get("مقدار"),
        "واحد": delivery.get("واحد"),
        "مرحله فعلی": stage,
        "تاریخ دستور": delivery.get("تاریخ تحویل"),
        "تاریخ تحویل": delivery.get("تاریخ تحویل"),
        "شماره مجوز ورود": delivery_num,
        "شماره تحویل": delivery_num,
        "وضعیت": status,
        "تحویل گیرنده": delivery.get("تحویل گیرنده"),
        "توضیحات": delivery.get("توضیحات"),
        "_from_delivery": True,
    }


def _workflow_response(order: Dict, *, source: str = "order", note: str = "") -> Dict:
    order = _migrate_legacy_order_fields(order)
    meta = workflow_meta(str(order.get("مرحله فعلی") or "دستور خرید"), order)
    payload: Dict = {"ok": True, "order": order, "workflow": meta, "source": source}
    if note:
        payload["note"] = note
    return json_safe(payload)


def get_order_workflow(order_id: str) -> Dict:
    order = _get_order_row(order_id)
    if not order:
        raise ValueError("دستور یافت نشد")
    return _workflow_response(order)


def get_order_workflow_by_number(order_number: str) -> Dict:
    order = local_storage.find_order_by_number(order_number)
    if order:
        return get_order_workflow(str(order.get("id")))

    delivery = local_storage.find_delivery_by_order(order_number)
    if delivery:
        synthetic = _synthesize_order_from_delivery(delivery)
        return _workflow_response(
            synthetic,
            source="delivery",
            note="رکورد دستور جداگانه ثبت نشده — اطلاعات از تحویل import‌شده",
        )

    raise ValueError("دستور یافت نشد — تحویل مرتبطی هم یافت نشد")


def get_delivery_workflow(delivery_id: str) -> Dict:
    delivery = local_storage.find_delivery_by_id(delivery_id)
    if not delivery:
        raise ValueError("تحویل یافت نشد")
    order_num = str(delivery.get("شماره دستور") or "").strip()
    if order_num:
        order = local_storage.find_order_by_number(order_num)
        if order:
            return get_order_workflow(str(order.get("id")))
    return _workflow_response(
        _synthesize_order_from_delivery(delivery),
        source="delivery",
        note="رکورد دستور جداگانه ثبت نشده — اطلاعات از تحویل",
    )


def _clean_delivery_val(val: Any) -> Any:
    if val is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(val):
            return ""
    except Exception:
        pass
    text = str(val).strip()
    return "" if text.lower() in ("nan", "none") else val


def _notify_warehouse_if_delivered(order: Dict) -> None:
    from services.warehouse_resolver import resolve_warehouse_from_order

    order = _migrate_legacy_order_fields(order)
    if not is_delivery_completed(order):
        return
    warehouse = resolve_warehouse_from_order(order)
    order_num = str(order.get("شماره دستور") or "")
    product = str(order.get("عنوان کالا") or "")
    notification_service.notify_warehouse_delivery(
        warehouse,
        "تحویل شده",
        f"خرید {order_num} — {product} — مجوز و تاریخ ثبت شد",
        str(order.get("id", order_num)),
    )


def _delivery_payload_from_order(order: Dict) -> Dict:
    permit = str(order.get("شماره مجوز ورود") or "").strip()
    order_num = str(order.get("شماره دستور") or "").strip()
    delivery_number = permit or (f"DL-{order_num}" if order_num else "")
    qty = order.get("تعداد")
    if qty is not None:
        try:
            import pandas as pd
            if pd.isna(qty):
                qty = None
        except Exception:
            pass
    return {
        "شماره تحویل": delivery_number,
        "شماره دستور": order_num,
        "شماره خرید": _clean_delivery_val(order.get("شماره خرید")),
        "عنوان کالا": _clean_delivery_val(order.get("عنوان کالا")),
        "انبار": _clean_delivery_val(order.get("انبار")),
        "مقدار": qty,
        "واحد": _clean_delivery_val(order.get("واحد")),
        "تاریخ تحویل": _clean_delivery_val(order.get("تاریخ تحویل")),
        "تحویل گیرنده": "",
        "وضعیت": "ثبت شده",
        "توضیحات": f"مجوز ورود: {permit}" if permit else f"ثبت از دستور {order_num}",
    }


def _sync_delivery_from_order(order: Dict, username: str) -> Optional[Dict]:
    from services import delivery_service

    order_num = str(order.get("شماره دستور") or "").strip()
    if not order_num:
        return None
    payload = _delivery_payload_from_order(order)
    if not payload.get("شماره تحویل"):
        return None

    existing = local_storage.find_delivery_by_order(order_num)
    if existing:
        updates = {
            k: payload[k]
            for k in ("شماره تحویل", "تاریخ تحویل", "مقدار", "واحد", "عنوان کالا", "انبار", "توضیحات")
            if payload.get(k) is not None
        }
        return delivery_service.update_delivery(
            str(existing.get("id")), updates, username, notify=False
        ).get("delivery")

    try:
        return delivery_service.create_delivery(payload, username, notify=False).get("delivery")
    except ValueError as exc:
        if "تکراری" in str(exc):
            return existing
        raise


def edit_completed_stage(order_id: str, stage_name: str, payload: Dict, username: str) -> Dict:
    from services import history_service

    before = _get_order_row(order_id)
    if not before:
        raise ValueError("دستور یافت نشد")
    before = _migrate_legacy_order_fields(before)

    stage = normalize_stage(stage_name)
    if stage == "دستور خرید":
        raise ValueError("مرحله دستور خرید قابل ویرایش نیست")

    current = normalize_stage(before.get("مرحله فعلی"))
    if not is_stage_completed(current, stage):
        raise ValueError(f"مرحله «{stage}» هنوز ثبت نشده است")

    required = STAGE_REQUIRED_FIELDS.get(stage, [])
    updates: Dict = {}
    for field in required:
        val = str(payload.get(field) or "").strip()
        if not val:
            raise ValueError(f"«{field}» برای مرحله «{stage}» الزامی است")
        updates[field] = val

    result = local_storage.update_order(order_id, updates, username)
    if not result:
        raise ValueError("دستور یافت نشد")
    result = _migrate_legacy_order_fields(result)

    delivery = None
    if stage == "تحویل":
        delivery = _sync_delivery_from_order(result, username)
        _notify_warehouse_if_delivered(result)

    entity_id = str(before.get("شماره دستور") or order_id)
    history_service.log_field_changes("دستور خرید", entity_id, username, updates, before)
    history_service.log_action("دستور خرید", entity_id, username, "ویرایش مرحله", f"مرحله «{stage}»")

    invalidate_cache()
    return json_safe({
        "ok": True,
        "order": result,
        "delivery": delivery,
        "workflow": workflow_meta(str(result.get("مرحله فعلی") or current), result),
    })


def advance_order_stage(order_id: str, payload: Dict, username: str) -> Dict:
    from services import history_service

    before = _get_order_row(order_id)
    if not before:
        raise ValueError("دستور یافت نشد")
    before = _migrate_legacy_order_fields(before)

    current = normalize_stage(before.get("مرحله فعلی"))
    if order_is_delivered(before):
        raise ValueError("این دستور به مرحله پایانی (تحویل) رسیده — فقط مشاهده امکان‌پذیر است")

    target = next_stage_to_complete(current)
    if not target:
        raise ValueError("مرحله بعدی برای این دستور وجود ندارد")

    required = STAGE_REQUIRED_FIELDS.get(target, [])
    updates: Dict = {}
    for field in required:
        val = str(payload.get(field) or "").strip()
        if not val:
            raise ValueError(f"«{field}» برای مرحله «{target}» الزامی است")
        updates[field] = val

    for field in locked_fields_for(target):
        if field not in payload:
            continue
        new_val = str(payload.get(field) or "").strip()
        old_val = str(before.get(field) or "").strip()
        if new_val and old_val and new_val != old_val:
            raise ValueError(f"امکان ویرایش «{field}» از مراحل قبل وجود ندارد")

    note = str(payload.get("توضیحات") or "").strip()
    if note:
        prev = str(before.get("توضیحات") or "").strip()
        updates["توضیحات"] = f"{prev}\n{note}".strip() if prev else note

    updates["مرحله فعلی"] = target
    if target == "تحویل":
        updates["وضعیت"] = "تحویل شده"
    elif str(before.get("وضعیت") or "") in ("", "صدور دستور", "None", "nan"):
        updates["وضعیت"] = "در جریان"

    result = local_storage.update_order(order_id, updates, username)
    if not result:
        raise ValueError("دستور یافت نشد")

    entity_id = str(before.get("شماره دستور") or order_id)
    history_service.log_field_changes("دستور خرید", entity_id, username, updates, before)
    history_service.log_action(
        "دستور خرید",
        entity_id,
        username,
        "ثبت مرحله",
        f"مرحله «{target}» تکمیل شد",
    )

    delivery = None
    if target == "تحویل":
        delivery = _sync_delivery_from_order(_migrate_legacy_order_fields(result), username)

    if target == "تحویل":
        _notify_warehouse_if_delivered(_migrate_legacy_order_fields(result))
    invalidate_cache()
    return json_safe({
        "ok": True,
        "order": _migrate_legacy_order_fields(result),
        "delivery": delivery,
        "workflow": workflow_meta(str(result.get("مرحله فعلی") or target), result),
    })


def sync_deliveries_for_completed_orders(username: str = "system") -> int:
    """دستورهای خاتمه‌یافته بدون رکورد تحویل را همگام می‌کند."""
    orders_df = local_storage.get_orders()
    if orders_df.empty:
        return 0
    count = 0
    for _, row in orders_df.iterrows():
        order = _migrate_legacy_order_fields(row.to_dict())
        if not is_delivery_completed(order):
            continue
        before = local_storage.find_delivery_by_order(str(order.get("شماره دستور") or ""))
        result = _sync_delivery_from_order(order, username)
        if result and not before:
            count += 1
    if count:
        invalidate_cache()
    return count


def update_order_stage(order_id: str, payload: Dict, username: str) -> Dict:
    edit_stage = str(payload.get("edit_stage") or "").strip()
    if edit_stage:
        clean = {k: v for k, v in payload.items() if k != "edit_stage"}
        return edit_completed_stage(order_id, edit_stage, clean, username)
    return advance_order_stage(order_id, payload, username)