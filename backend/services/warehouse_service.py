"""خدمات کاربر انبار — استعلام کالا، خریدهای ثبت‌شده، داشبورد."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from services import local_storage
from services.excel_service import (
    _clean,
    _get_merged_purchases,
    _json_safe,
    _normalize_id,
    purchase_flow_status,
)
from services.order_stages import STAGE_VIEW_FIELDS, normalize_stage, order_is_delivered
from services.warehouse_resolver import normalize_warehouse, warehouses_match

WAREHOUSE_STAGE_LABELS = [
    "ثبت استعلام",
    "دستور خرید",
    "سفارش",
    "ثبت پرداخت",
    "تبدیل وضعیت پرداخت",
    "تحویل",
]


def _match_product_mask(df: pd.DataFrame, code: str, title: str) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    if code and "کد قلم خریدنی" in df.columns:
        mask &= df["کد قلم خریدنی"].astype(str).str.contains(code, case=False, na=False)
    if title and "عنوان قلم خریدنی" in df.columns:
        mask &= df["عنوان قلم خریدنی"].astype(str).str.contains(title, case=False, na=False)
    return mask


def _warehouse_purchase_ids(warehouse: str) -> set:
    wh = normalize_warehouse(warehouse)
    out: set = set()
    issued = local_storage.get_issued_inquiries()
    if not issued.empty and "انبار" in issued.columns:
        m = issued[issued["انبار"].astype(str).map(normalize_warehouse) == wh]
        if "شماره درخواست خرید" in m.columns:
            out.update(m["شماره درخواست خرید"].map(_normalize_id).tolist())
    orders = local_storage.get_orders()
    if not orders.empty and "انبار" in orders.columns:
        m = orders[orders["انبار"].astype(str).map(normalize_warehouse) == wh]
        if "شماره خرید" in m.columns:
            out.update(m["شماره خرید"].map(_normalize_id).tolist())
    return out


def _last_purchases_list(code: str, title: str, limit: int = 10) -> List[Dict]:
    rows: List[Dict] = []
    hist = local_storage.get_product_history()
    if hist.empty:
        return rows
    mask = pd.Series(False, index=hist.index)
    if code and "کد قلم خریدنی" in hist.columns:
        mask |= hist["کد قلم خریدنی"].astype(str).str.strip() == code
    if title and "عنوان کالا" in hist.columns:
        mask |= hist["عنوان کالا"].astype(str).str.contains(title, case=False, na=False)
    matched = hist[mask].copy()
    if matched.empty:
        return rows
    if "فی" in matched.columns:
        matched = matched[pd.to_numeric(matched["فی"], errors="coerce").fillna(0) > 0]
    if "created_at" in matched.columns:
        matched = matched.sort_values("created_at", ascending=False, na_position="last")
    for _, row in matched.head(limit).iterrows():
        rows.append({
            "عنوان کالا": _clean(row.get("عنوان کالا")),
            "کد قلم خریدنی": _clean(row.get("کد قلم خریدنی")),
            "فی": _clean(row.get("فی")),
            "تعداد": _clean(row.get("تعداد")),
            "واحد": _clean(row.get("واحد")),
            "تامین‌کننده": _clean(row.get("نام پیمانکار")),
            "شهر": _clean(row.get("شهر پیمانکار")),
            "شماره خرید": _clean(row.get("شماره خرید")),
            "شماره استعلام": _clean(row.get("شماره استعلام")),
            "تاریخ": _clean(str(row.get("تاریخ خرید") or row.get("created_at") or "")[:10]),
        })
    return rows


def _orders_for_product(warehouse: str, code: str, title: str) -> List[Dict]:
    orders = local_storage.get_orders()
    if orders.empty:
        return []
    wh = str(warehouse).strip()
    df = orders[orders["انبار"].astype(str).map(normalize_warehouse) == wh] if "انبار" in orders.columns else orders.iloc[0:0]
    if df.empty:
        return []
    mask = pd.Series(True, index=df.index)
    if title and "عنوان کالا" in df.columns:
        mask &= df["عنوان کالا"].astype(str).str.contains(title, case=False, na=False)
    if code:
        purchase_ids = set()
        purchases = _get_merged_purchases()
        if not purchases.empty:
            pm = _match_product_mask(purchases, code, "")
            purchase_ids = set(purchases.loc[pm, "شماره"].map(_normalize_id).tolist()) if pm.any() else set()
        if purchase_ids and "شماره خرید" in df.columns:
            mask &= df["شماره خرید"].map(_normalize_id).isin(purchase_ids)
        elif title:
            pass
        else:
            mask &= False
    result = []
    for _, row in df[mask].iterrows():
        stage = normalize_stage(row.get("مرحله فعلی"))
        result.append({
            "شماره دستور": _clean(row.get("شماره دستور")),
            "شماره استعلام": _clean(row.get("شماره استعلام")),
            "شماره خرید": _clean(row.get("شماره خرید")),
            "عنوان کالا": _clean(row.get("عنوان کالا")),
            "مرحله فعلی": _clean(row.get("مرحله فعلی")),
            "وضعیت": "تحویل شده" if order_is_delivered(row.to_dict()) else _clean(row.get("وضعیت") or stage),
            "تاریخ دستور": _clean(row.get("تاریخ دستور")),
            "کارشناس": _clean(row.get("کارشناس")),
            "پیمانکار": _clean(row.get("نام پیمانکار")),
        })
    return result


def lookup_product(warehouse: str, product_code: str = "", product_title: str = "") -> Dict[str, Any]:
    code = str(product_code or "").strip()
    title = str(product_title or "").strip()
    if not code and not title:
        raise ValueError("حداقل کد قلم خریدنی یا عنوان کالا را وارد کنید")

    wh = normalize_warehouse(warehouse)
    if not wh:
        raise ValueError("انبار کاربر مشخص نیست")

    df = _get_merged_purchases()
    if df.empty:
        return _empty_result(wh, code, title)

    matched = df[_match_product_mask(df, code, title)]
    wh_purchases = _warehouse_purchase_ids(wh)

    purchase_requests: List[Dict] = []
    material_requests: List[Dict] = []
    seen_mabna: set = set()

    for _, row in matched.iterrows():
        pn = _normalize_id(row.get("شماره"))
        if pn not in wh_purchases:
            continue
        rec = {k: _clean(v) for k, v in row.to_dict().items() if not str(k).startswith("_")}
        rec["شماره خرید"] = pn
        purchase_requests.append(rec)
        mabna = _clean(row.get("شماره مبنا"))
        if mabna and mabna not in seen_mabna:
            seen_mabna.add(mabna)
            material_requests.append({
                "شماره درخواست کالا": mabna,
                "شماره خرید": pn,
                "عنوان قلم": _clean(row.get("عنوان قلم خریدنی")),
                "کد قلم": _clean(row.get("کد قلم خریدنی")),
                "تاریخ درخواست": _clean(row.get("تاریخ درخواست کالا")),
                "وضعیت": _clean(row.get("وضعیت")),
            })

    last_purchases = _last_purchases_list(code, title)
    orders = _orders_for_product(wh, code, title)

    has_material = len(material_requests) > 0
    has_purchases = len(purchase_requests) > 0
    has_last = len(last_purchases) > 0

    parts = []
    if has_material:
        parts.append(f"برای این کالا {len(material_requests)} درخواست ثبت قلم (درخواست کالا) در انبار «{wh}» دارید")
    else:
        parts.append(f"درخواست ثبت قلمی برای این کالا در انبار «{wh}» یافت نشد")
    if has_purchases:
        parts.append(f"{len(purchase_requests)} درخواست خرید مرتبط")
    if has_last:
        parts.append(f"آخرین خرید: {last_purchases[0].get('تامین‌کننده') or '—'} — {last_purchases[0].get('فی') or '—'} ریال")
    else:
        parts.append("سابقه خرید ثبت‌شده‌ای برای این کالا نیست")

    return _json_safe({
        "warehouse": wh,
        "query": {"code": code, "title": title},
        "summary": " · ".join(parts),
        "has_material_requests": has_material,
        "has_purchase_requests": has_purchases,
        "has_last_purchases": has_last,
        "material_requests": material_requests,
        "purchase_requests": purchase_requests,
        "last_purchases": last_purchases,
        "orders": orders,
    })


def _empty_result(wh: str, code: str, title: str) -> Dict:
    return {
        "warehouse": wh,
        "query": {"code": code, "title": title},
        "summary": "داده‌ای یافت نشد",
        "has_material_requests": False,
        "has_purchase_requests": False,
        "has_last_purchases": False,
        "material_requests": [],
        "purchase_requests": [],
        "last_purchases": _last_purchases_list(code, title),
        "orders": [],
    }


def _purchase_row_for_number(purchases: pd.DataFrame, purchase_number: str) -> Dict:
    if purchases.empty or "شماره" not in purchases.columns:
        return {}
    pn = _normalize_id(purchase_number)
    m = purchases[purchases["شماره"].map(_normalize_id) == pn]
    if m.empty:
        return {}
    row = m.iloc[0]
    return {k: _clean(v) for k, v in row.to_dict().items() if not str(k).startswith("_")}


def _order_for_inquiry(orders: pd.DataFrame, inquiry_number: str) -> Optional[Dict]:
    if orders.empty or "شماره استعلام" not in orders.columns:
        return None
    m = orders[orders["شماره استعلام"].astype(str) == str(inquiry_number)]
    if m.empty:
        return None
    row = m.sort_values("created_at", ascending=False, na_position="last").iloc[0]
    return {k: _clean(v) for k, v in row.to_dict().items() if not str(k).startswith("_")}


def build_stage_timeline(inquiry: Dict, order: Optional[Dict]) -> List[Dict]:
    """فقط مراحل — بدون فرم ویرایش."""
    inq_date = inquiry.get("تاریخ استعلام") or inquiry.get("created_at")
    timeline: List[Dict] = [{
        "stage": "ثبت استعلام",
        "status": "done",
        "details": {"تاریخ استعلام": _clean(inq_date)},
    }]
    if not order:
        for label in WAREHOUSE_STAGE_LABELS[1:]:
            timeline.append({"stage": label, "status": "pending", "details": {}})
        timeline[1]["status"] = "current"
        return timeline

    stage = normalize_stage(order.get("مرحله فعلی"))
    stage_idx = WAREHOUSE_STAGE_LABELS.index(stage) if stage in WAREHOUSE_STAGE_LABELS else 1

    for i, label in enumerate(WAREHOUSE_STAGE_LABELS[1:], start=1):
        fields = STAGE_VIEW_FIELDS.get(label, [])
        details = {f: _clean(order.get(f)) for f in fields if _clean(order.get(f))}
        if i < stage_idx:
            st = "done"
        elif i == stage_idx:
            st = "done" if order_is_delivered(order) else "current"
        else:
            st = "pending"
        timeline.append({"stage": label, "status": st, "details": details})

    if order_is_delivered(order):
        for item in timeline:
            if item["stage"] != "ثبت استعلام":
                item["status"] = "done"

    return timeline


def get_purchase_stages(warehouse: str, inquiry_number: str) -> Dict[str, Any]:
    wh = str(warehouse).strip()
    issued = local_storage.get_issued_inquiries()
    if issued.empty:
        raise ValueError("استعلام یافت نشد")
    m = issued[issued["شماره استعلام"].astype(str) == str(inquiry_number)]
    if m.empty:
        raise ValueError("استعلام یافت نشد")
    inquiry = {k: _clean(v) for k, v in m.iloc[0].to_dict().items()}
    if not warehouses_match(inquiry.get("انبار"), wh):
        raise ValueError("این خرید به انبار شما مرتبط نیست")

    orders = local_storage.get_orders()
    order = _order_for_inquiry(orders, inquiry_number)
    purchases = _get_merged_purchases()
    pn = _normalize_id(inquiry.get("شماره درخواست خرید"))
    purchase = _purchase_row_for_number(purchases, pn)

    return _json_safe({
        "inquiry_number": inquiry_number,
        "purchase_number": pn,
        "warehouse": wh,
        "عنوان کالا": purchase.get("عنوان قلم خریدنی") or order.get("عنوان کالا") if order else purchase.get("عنوان قلم خریدنی"),
        "کد قلم خریدنی": purchase.get("کد قلم خریدنی"),
        "وضعیت جریان": purchase_flow_status(pn, str(purchase.get("عنوان قلم خریدنی") or "")),
        "مرحله فعلی": order.get("مرحله فعلی") if order else "ثبت استعلام",
        "شماره دستور": order.get("شماره دستور") if order else None,
        "stages": build_stage_timeline(inquiry, order),
    })


def list_registered_purchases(
    warehouse: str,
    search: str = "",
    stage_filter: str = "",
    expert: str = "",
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    wh = str(warehouse).strip()
    issued = local_storage.get_issued_inquiries()
    if issued.empty or "انبار" not in issued.columns:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    df = issued[issued["انبار"].astype(str).map(normalize_warehouse) == wh].copy()

    orders = local_storage.get_orders()
    purchases = _get_merged_purchases()
    items: List[Dict] = []

    for _, inq in df.iterrows():
        inq_num = str(inq.get("شماره استعلام", ""))
        pn = _normalize_id(inq.get("شماره درخواست خرید"))
        purchase = _purchase_row_for_number(purchases, pn)
        order = _order_for_inquiry(orders, inq_num)
        title = str(purchase.get("عنوان قلم خریدنی") or (order or {}).get("عنوان کالا") or "")
        flow = purchase_flow_status(pn, title)
        current_stage = normalize_stage((order or {}).get("مرحله فعلی")) if order else "ثبت استعلام"
        delivered = order_is_delivered(order) if order else False
        items.append({
            "id": inq_num,
            "شماره استعلام": inq_num,
            "شماره خرید": pn,
            "عنوان کالا": _clean(title) or "—",
            "کد قلم خریدنی": _clean(purchase.get("کد قلم خریدنی")),
            "وضعیت جریان": flow,
            "مرحله فعلی": "تحویل شده" if delivered else current_stage,
            "تحویل_کامل": delivered,
            "تاریخ استعلام": _clean(inq.get("تاریخ استعلام")),
            "کارشناس خرید": _clean(inq.get("کارشناس خرید") or inq.get("صادر کننده سند")),
            "شماره دستور": _clean((order or {}).get("شماره دستور")),
            "order_id": _clean((order or {}).get("id")),
        })

    if stage_filter.strip():
        st = stage_filter.strip()
        items = [i for i in items if str(i.get("مرحله فعلی") or "") == st]
    if expert.strip():
        ex = expert.strip()
        items = [i for i in items if ex in str(i.get("کارشناس خرید") or "")]

    if search.strip():
        q = search.strip().lower()
        items = [
            i for i in items
            if q in " ".join(
                str(i.get(k) or "")
                for k in ("شماره استعلام", "شماره خرید", "عنوان کالا", "کد قلم خریدنی", "مرحله فعلی", "کارشناس خرید", "شماره دستور")
            ).lower()
        ]

    items.sort(key=lambda x: str(x.get("تاریخ استعلام") or ""), reverse=True)
    total = len(items)
    page = max(1, page)
    page_size = max(10, min(page_size, 200))
    start = (page - 1) * page_size
    chunk = items[start : start + page_size]
    pages = math.ceil(total / page_size) if total else 0
    return _json_safe({
        "items": chunk,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": pages,
    })


def _monthly_trend(items: List[Dict]) -> Dict[str, int]:
    trend: Dict[str, int] = {}
    for it in items:
        raw = str(it.get("تاریخ استعلام") or "").strip()
        if not raw:
            continue
        key = raw[:7] if len(raw) >= 7 else raw
        trend[key] = trend.get(key, 0) + 1
    return dict(sorted(trend.items()))


def get_warehouse_dashboard(warehouse: str) -> Dict[str, Any]:
    wh = str(warehouse).strip()
    items = list_registered_purchases(wh, page=1, page_size=5000).get("items") or []

    by_stage: Dict[str, int] = {}
    awaiting_delivery = delivered = 0

    for it in items:
        if it.get("تحویل_کامل"):
            delivered += 1
            stage_key = "تحویل شده"
        else:
            stage_key = str(it.get("مرحله فعلی") or "ثبت استعلام")
            if stage_key == "تحویل":
                awaiting_delivery += 1
        by_stage[stage_key] = by_stage.get(stage_key, 0) + 1

    summary = warehouse_status_summary(wh)
    total = len(items)
    stage_order = WAREHOUSE_STAGE_LABELS + ["تحویل شده"] + [s for s in by_stage if s not in WAREHOUSE_STAGE_LABELS and s != "تحویل شده"]
    stage_cards = [{"stage": s, "count": by_stage.get(s, 0)} for s in stage_order if by_stage.get(s)]

    cards = [
        {"key": "registered", "label": "خریدهای ثبت‌شده", "value": total, "unit": "مورد", "hint": f"انبار {wh}"},
        {"key": "awaiting_delivery", "label": "در انتظار تحویل", "value": awaiting_delivery, "unit": "مورد", "hint": "مرحله تحویل — مجوز یا تاریخ ناقص"},
        {"key": "delivered", "label": "تحویل‌شده", "value": delivered, "unit": "مورد", "hint": "دارای شماره مجوز ورود و تاریخ تحویل"},
    ]

    experts = sorted({str(i.get("کارشناس خرید") or "").strip() for i in items if str(i.get("کارشناس خرید") or "").strip()})
    stages_seen = [s for s in WAREHOUSE_STAGE_LABELS if s in by_stage]
    stages_seen += [s for s in by_stage if s not in stages_seen]

    return _json_safe({
        "warehouse": wh,
        "stats": {"total": total, "delivered": delivered, "awaiting_delivery": awaiting_delivery},
        "by_stage": by_stage,
        "stage_cards": stage_cards,
        "trend": _monthly_trend(items),
        "kpis": {"cards": cards},
        "recent_items": items[:12],
        "table_items": items,
        "filter_options": {"stages": stages_seen, "experts": experts},
        "summary": summary,
    })


def _warehouse_delivery_completed_count(warehouse: str) -> int:
    items = list_registered_purchases(warehouse, page=1, page_size=5000).get("items") or []
    return sum(1 for it in items if it.get("تحویل_کامل"))


def warehouse_status_summary(warehouse: str) -> Dict[str, Any]:
    wh = normalize_warehouse(warehouse)
    orders = local_storage.get_orders()
    open_orders = delivered = 0
    if not orders.empty and "انبار" in orders.columns:
        wh_orders = orders[orders["انبار"].astype(str).map(normalize_warehouse) == wh]
        for _, row in wh_orders.iterrows():
            rec = row.to_dict()
            if order_is_delivered(rec):
                delivered += 1
            else:
                open_orders += 1
    delivery_count = _warehouse_delivery_completed_count(wh)
    return _json_safe({
        "warehouse": wh,
        "open_orders": open_orders,
        "delivered_orders": delivered,
        "deliveries": delivery_count,
    })