"""خروجی اکسل برای بخش‌های مدیریتی."""

from __future__ import annotations

import math
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd

from config import MANAGER_ROLES
from services import (
    analytics_service,
    delivery_service,
    excel_service,
    history_service,
    inquiry_service,
    order_service,
)


EXPORTABLE_VIEWS = {
    "requests",
    "inquiries",
    "inquiry_review",
    "my_inquiries",
    "orders",
    "deliveries",
    "report_reorder",
    "report_purchase",
    "report_expert",
    "report_my",
    "report_duration",
    "history",
    "dashboard",
    "warehouse_dashboard",
    "warehouse_purchases",
}


def _expert_filter(user: dict, expert: Optional[str]) -> Optional[str]:
    if user.get("role") == "expert":
        return user.get("expert")
    return expert


def _is_manager(user: dict) -> bool:
    return user.get("role") in MANAGER_ROLES


def _rows_to_xlsx(rows: List[Dict], sheet_name: str) -> bytes:
    buf = BytesIO()
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return buf.getvalue()


def _flatten_report_purchase(data: dict) -> List[Dict]:
    rows: List[Dict] = []
    for section, key in (
        ("وضعیت", "status_breakdown"),
        ("نوع خرید", "purchase_type_breakdown"),
        ("اولویت", "urgency_breakdown"),
    ):
        for label, count in (data.get(key) or {}).items():
            rows.append({"بخش": section, "عنوان": label, "تعداد": count})
    rows.insert(0, {"بخش": "خلاصه", "عنوان": "کل اقلام", "تعداد": data.get("total_amount_items", 0)})
    return rows


def _flatten_duration(data: dict) -> List[Dict]:
    rows: List[Dict] = []
    for stage, info in (data.get("summary") or {}).items():
        rows.append({
            "بخش": "خلاصه مراحل",
            "مرحله": stage,
            "میانگین روز": info.get("avg_days"),
            "تعداد": info.get("count"),
            "انبار": "",
            "کالا/خرید": "",
        })
    for wh, stages in (data.get("by_warehouse") or {}).items():
        for stage, info in stages.items():
            rows.append({
                "بخش": "تفکیک انبار",
                "مرحله": stage,
                "میانگین روز": info.get("avg_days"),
                "تعداد": info.get("count"),
                "انبار": wh,
                "کالا/خرید": "",
            })
    for prod in data.get("by_product") or []:
        for stage, info in (prod.get("stages") or {}).items():
            rows.append({
                "بخش": "تفکیک کالا",
                "مرحله": stage,
                "میانگین روز": info.get("avg_days"),
                "تعداد": info.get("count"),
                "انبار": "",
                "کالا/خرید": prod.get("product"),
            })
    for period_key, avg_days in (data.get("trend") or {}).items():
        rows.append({
            "بخش": "روند زمانی",
            "مرحله": period_key,
            "میانگین روز": avg_days,
            "تعداد": "",
            "انبار": "",
            "کالا/خرید": "",
        })
    return rows


def _flatten_report_expert(data: dict) -> List[Dict]:
    rows: List[Dict] = []
    for row in data.get("summary") or []:
        rows.append({
            "بخش": "خلاصه کارشناس",
            "کارشناس خرید": row.get("کارشناس خرید"),
            "کل خرید": row.get("total"),
            "در جریان": row.get("in_progress"),
            "بسته": row.get("closed"),
            "معلق": row.get("suspended"),
            "استعلام صادر": row.get("inquiry_issued"),
            "دستور": row.get("orders"),
            "تحویل": row.get("deliveries"),
            "مقدار تحویل شده": row.get("delivered_qty"),
            "جریان — استعلام": row.get("flow_inquiry"),
            "جریان — دستور": row.get("flow_ordered"),
            "جریان — تحویل": row.get("flow_delivered"),
            "مبلغ درخواست": row.get("requested_amount"),
            "مبلغ دستور": row.get("ordered_amount"),
            "مبلغ تحویل‌شده": row.get("delivered_amount"),
            "مبلغ باقیمانده": row.get("pending_amount"),
        })
    for row in data.get("items") or []:
        rows.append({"بخش": "جزئیات", **row})
    return rows


def _flatten_dashboard(data: dict) -> List[Dict]:
    rows: List[Dict] = []
    for card in (data.get("kpis") or {}).get("cards") or []:
        rows.append({
            "شاخص": card.get("label"),
            "مقدار": card.get("value"),
            "واحد": card.get("unit"),
            "توضیح": card.get("hint"),
        })
    for status, cnt in (data.get("stats") or {}).get("by_status", {}).items():
        rows.append({"شاخص": f"وضعیت — {status}", "مقدار": cnt, "واحد": "قلم", "توضیح": ""})
    return rows


def collect_export_rows(
    view: str,
    user: dict,
    *,
    search: str = "",
    filter_type: str = "",
    expert: str = "",
    status: str = "",
    warehouse: str = "",
    urgency: str = "",
    purchase_type: str = "",
    period: str = "month",
    entity_type: str = "",
    entity_id: str = "",
) -> List[Dict]:
    exp = _expert_filter(user, expert or None)

    if view == "requests":
        res = excel_service.get_purchase_requests(
            search=search,
            filter_type=filter_type,
            expert=exp,
            urgency=urgency,
            purchase_type=purchase_type,
            export_all=True,
        )
        return res.get("items") or []

    if view in ("inquiries", "inquiry_review", "my_inquiries"):
        mine = view == "my_inquiries"
        review = view == "inquiry_review"
        return inquiry_service.list_local_inquiries(
            search=search,
            page=1,
            page_size=50000,
            user=user if mine else (user if review and user.get("role") == "expert" else None),
            expert=expert if not mine else "",
            status=status,
            warehouse=warehouse,
            exclude_moved_to_orders=mine,
        ).get("items") or []

    if view == "orders":
        return order_service.list_orders(
            search=search,
            page=1,
            page_size=50000,
            user=user,
            exclude_completed=False,
            page_cap=50000,
        ).get("items") or []

    if view == "deliveries":
        return delivery_service.list_deliveries(
            search=search, page=1, page_size=50000, user=user, page_cap=50000,
        ).get("items") or []

    if view == "report_reorder":
        return excel_service.get_reorder_report(
            page=1, page_size=50000, expert=exp,
        ).get("items") or []

    if view == "report_purchase":
        return _flatten_report_purchase(excel_service.get_purchase_summary(
            expert=exp, urgency=urgency, purchase_type=purchase_type,
        ))

    if view == "report_my":
        if user.get("role") != "expert":
            return []
        exp_name = user.get("expert") or user.get("name")
        return _flatten_report_expert(excel_service.get_expert_report(expert=exp_name))

    if view == "report_expert":
        if not _is_manager(user):
            return []
        return _flatten_report_expert(excel_service.get_expert_report(expert=expert or None))

    if view == "report_duration":
        if not _is_manager(user):
            return []
        return _flatten_duration(analytics_service.get_duration_dashboard(period=period))

    if view == "history":
        if user.get("role") != "admin":
            return []
        return history_service.list_history(
            search=search,
            entity_type=entity_type,
            entity_id=entity_id,
            page=1,
            page_size=50000,
            page_cap=50000,
        ).get("items") or []

    if view == "dashboard":
        return _flatten_dashboard(
            excel_service.get_dashboard(
                expert=exp,
                include_experts=_is_manager(user),
            )
        )

    if view == "warehouse_dashboard":
        if user.get("role") != "warehouse":
            return []
        from services import warehouse_service

        return _flatten_dashboard(warehouse_service.get_warehouse_dashboard(user.get("warehouse") or ""))

    if view == "warehouse_purchases":
        if user.get("role") != "warehouse":
            return []
        from services import warehouse_service

        return warehouse_service.list_registered_purchases(
            user.get("warehouse") or "",
            search=search,
            page=1,
            page_size=50000,
        ).get("items") or []

    return []


def export_view_xlsx(view: str, user: dict, **filters) -> tuple:
    if view not in EXPORTABLE_VIEWS:
        raise ValueError(f"نمای «{view}» قابل خروجی اکسل نیست")

    if view == "report_my" and user.get("role") != "expert":
        raise PermissionError("گزارش من فقط برای کارشناس است")
    if view in ("report_expert", "report_duration", "report_purchase", "report_reorder") and not _is_manager(user):
        raise PermissionError("دسترسی به این گزارش مجاز نیست")
    if view in ("report_purchase", "report_reorder") and user.get("role") == "warehouse":
        raise PermissionError("دسترسی به این گزارش مجاز نیست")
    if view == "history" and user.get("role") != "admin":
        raise PermissionError("فقط مدیر سیستم")

    titles = {
        "requests": "درخواست_خرید",
        "inquiries": "استعلام‌ها",
        "inquiry_review": "بررسی_استعلام",
        "my_inquiries": "استعلام‌های_من",
        "orders": "دستور_خرید",
        "deliveries": "تحویل‌ها",
        "report_reorder": "نقطه_سفارش",
        "report_purchase": "گزارش_خرید",
        "report_expert": "گزارش_کارشناس",
        "report_my": "گزارش_من",
        "report_duration": "مدت_مراحل",
        "history": "تاریخچه",
        "dashboard": "KPI_داشبورد",
        "warehouse_dashboard": "گزارش_انبار",
        "warehouse_purchases": "خریدهای_ثبت‌شده",
    }
    rows = collect_export_rows(view, user, **filters)
    sheet = titles.get(view, view)
    content = _rows_to_xlsx(rows, sheet)
    filename = f"tadarokat-{view}-{len(rows)}.xlsx"
    return content, filename