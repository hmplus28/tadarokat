"""شاخص‌های کلیدی عملکرد (KPI) — داشبورد مدیریت و کارشناس."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from services import analytics_service, local_storage

_kpi_cache: Dict[str, Tuple[tuple, dict]] = {}
from services.order_stages import normalize_stage, order_is_delivered


def _safe_pct(num: float, den: float) -> float:
    if not den:
        return 0.0
    return round(100.0 * num / den, 1)


def _order_counts(orders_df, expert: Optional[str] = None) -> Dict[str, int]:
    total = open_cnt = delivered = pending = 0
    if orders_df is None or orders_df.empty:
        return {"total": 0, "open": 0, "delivered": 0, "pending": 0}

    for _, row in orders_df.iterrows():
        if expert:
            ord_expert = str(row.get("کارشناس") or "")
            if expert not in ord_expert:
                continue
        total += 1
        if order_is_delivered(row.to_dict()):
            delivered += 1
        else:
            open_cnt += 1
            stage = normalize_stage(row.get("مرحله فعلی"))
            if stage in ("دستور خرید", "سفارش", ""):
                pending += 1
    return {"total": total, "open": open_cnt, "delivered": delivered, "pending": pending}


def _inquiry_counts(issued_df, expert: Optional[str] = None) -> Dict[str, int]:
    total = pending = approved = 0
    if issued_df is None or issued_df.empty:
        return {"total": 0, "pending": 0, "approved": 0}

    for _, row in issued_df.iterrows():
        if expert:
            matched = False
            for col in ("کارشناس خرید", "صادر کننده سند"):
                if expert in str(row.get(col) or ""):
                    matched = True
                    break
            if not matched:
                continue
        total += 1
        st = str(row.get("وضعیت") or "")
        if "تایید" in st:
            approved += 1
        elif "انتظار" in st or "بررسی" in st:
            pending += 1
    return {"total": total, "pending": pending, "approved": approved}


def get_kpis(expert: Optional[str] = None, include_experts: bool = True) -> Dict[str, Any]:
    from services.excel_service import _filter_expert_purchases, _get_merged_purchases, _workflow_cache_key

    cache_key = (_workflow_cache_key(), expert or "", include_experts)
    cached = _kpi_cache.get("main")
    if cached and cached[0] == cache_key:
        return cached[1]

    orders_df = local_storage.get_orders()
    issued_df = local_storage.get_issued_inquiries()
    deliveries_df = local_storage.get_deliveries()

    ord_c = _order_counts(orders_df, expert)
    inq_c = _inquiry_counts(issued_df, expert)

    delivery_count = 0
    if deliveries_df is not None and not deliveries_df.empty:
        delivery_count = len(deliveries_df)

    active_purchases = 0
    overdue_reorder = 0
    pending_issue = 0
    if expert:
        from services.excel_service import _enrich_purchase_inquiry_flags

        purchases_df = _filter_expert_purchases(_get_merged_purchases(), expert)
        if not purchases_df.empty:
            purchases_df = _enrich_purchase_inquiry_flags(purchases_df, expert=expert)
            has_inq = purchases_df["has_local_inquiry"].fillna(False).astype(bool) if "has_local_inquiry" in purchases_df.columns else pd.Series([False] * len(purchases_df))
            approved = purchases_df["inquiry_approved"].fillna(False).astype(bool) if "inquiry_approved" in purchases_df.columns else pd.Series([False] * len(purchases_df))
            pending_mask = ~has_inq & ~approved
            pending_issue = int(pending_mask.sum())
    else:
        purchases_df = _filter_expert_purchases(_get_merged_purchases(), expert)
        if not purchases_df.empty and "وضعیت" in purchases_df.columns:
            active_mask = purchases_df["وضعیت"].isin(["در جریان", "تایید شده", "معلق"])
            active_purchases = int(active_mask.sum())
            if "تاریخ نیاز" in purchases_df.columns:
                try:
                    import jdatetime
                    today = jdatetime.date.today().strftime("%Y/%m/%d")
                except ImportError:
                    from datetime import datetime
                    today = datetime.now().strftime("%Y/%m/%d")
                need = purchases_df["تاریخ نیاز"].astype(str).str.strip()
                overdue_mask = active_mask & need.lt(today) & need.ne("")
                overdue_reorder = int(overdue_mask.sum())

    timeline = analytics_service.get_expert_stage_timeline(expert) if expert else {}
    stage_avgs = timeline.get("stages") or []
    avg_cycle = 0.0
    if stage_avgs:
        weighted = sum(s.get("avg_days", 0) * s.get("count", 0) for s in stage_avgs)
        count = sum(s.get("count", 0) for s in stage_avgs)
        avg_cycle = round(weighted / count, 1) if count else 0.0
    elif not orders_df.empty:
        from services.analytics_service import _days_between

        cycle_vals = []
        for _, row in orders_df.iterrows():
            if expert and expert not in str(row.get("کارشناس") or ""):
                continue
            d = _days_between(row.get("تاریخ دستور"), row.get("تاریخ تحویل"))
            if d is not None:
                cycle_vals.append(d)
        avg_cycle = round(sum(cycle_vals) / len(cycle_vals), 1) if cycle_vals else 0.0

    completion_rate = _safe_pct(ord_c["delivered"], ord_c["total"])

    cards: List[Dict[str, Any]] = [
        {
            "key": "completion_rate",
            "label": "نرخ تکمیل دستور",
            "value": completion_rate,
            "unit": "٪",
            "hint": f"{ord_c['delivered']} از {ord_c['total']} دستور",
        },
        {
            "key": "avg_cycle",
            "label": "میانگین چرخه",
            "value": avg_cycle,
            "unit": "روز",
            "hint": "میانگین مدت مراحل",
        },
        {
            "key": "open_inquiries",
            "label": "استعلام باز",
            "value": inq_c["pending"],
            "unit": "مورد",
            "hint": f"کل استعلام: {inq_c['total']}",
        },
        {
            "key": "open_orders",
            "label": "دستور در جریان",
            "value": ord_c["open"],
            "unit": "مورد",
            "hint": f"تحویل‌شده: {ord_c['delivered']}",
        },
        {
            "key": "active_purchases" if not expert else "pending_issue",
            "label": "خرید فعال" if not expert else "در انتظار صدور استعلام",
            "value": active_purchases if not expert else pending_issue,
            "unit": "قلم",
            "hint": "در جریان / تایید / معلق" if not expert else "بدون استعلام محلی",
        },
        {
            "key": "overdue_reorder",
            "label": "سررسید گذشته",
            "value": overdue_reorder if not expert else ord_c["open"],
            "unit": "قلم" if not expert else "مورد",
            "hint": "نقطه سفارش" if not expert else "دستور در جریان",
        },
        {
            "key": "deliveries",
            "label": "تحویل ثبت‌شده",
            "value": delivery_count,
            "unit": "مورد",
            "hint": "کل تحویل‌ها",
        },
    ]

    if expert:
        cards.append({
            "key": "my_items",
            "label": "موارد من",
            "value": timeline.get("item_count") or 0,
            "unit": "مورد",
            "hint": "ارجاع‌شده به شما",
        })

    result = {
        "completion_rate": completion_rate,
        "avg_cycle_days": avg_cycle,
        "open_inquiries": inq_c["pending"],
        "open_orders": ord_c["open"],
        "delivered_orders": ord_c["delivered"],
        "active_purchases": active_purchases,
        "overdue_reorder": overdue_reorder,
        "delivery_count": delivery_count,
        "cards": cards,
    }
    _kpi_cache["main"] = (cache_key, result)
    return result


def invalidate_kpi_cache() -> None:
    _kpi_cache.clear()