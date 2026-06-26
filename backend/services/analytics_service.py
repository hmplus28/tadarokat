import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from services import local_storage


def _parse_date(val: Any) -> Optional[datetime]:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    s = str(val).strip()[:19].replace("-", "/")
    if not s or s.lower() in ("nan", "none", ""):
        return None

    date_part = s.split()[0]
    parts = date_part.split("/")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if 1300 <= y <= 1500:
                import jdatetime

                jd = jdatetime.datetime(y, m, d)
                return jd.togregorian()
        except (ValueError, TypeError, OverflowError):
            pass

    for fmt in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _days_between(a: Any, b: Any) -> Optional[float]:
    d1, d2 = _parse_date(a), _parse_date(b)
    if not d1 or not d2:
        return None
    days = abs((d2 - d1).days)
    if days > 3650:
        return None
    return float(days)


def _period_key(date_val: Any, period: str) -> str:
    s = str(date_val or "").strip()
    if not s:
        return ""
    if period == "year":
        return s[:4]
    if period == "quarter":
        ym = s[:7]
        if len(ym) >= 7 and "/" in ym:
            try:
                y, m = ym.split("/")[:2]
                q = (int(m) - 1) // 3 + 1
                return f"{y}-Q{q}"
            except ValueError:
                pass
        return ym[:7]
    if period == "all":
        return "همه"
    return s[:7]


def get_duration_dashboard(period: str = "month") -> Dict:
    inquiries = local_storage.get_issued_inquiries()
    orders = local_storage.get_orders()
    pre_df = local_storage.get_pre_invoices()

    stage_avgs: Dict[str, List[float]] = defaultdict(list)
    by_warehouse: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    by_product: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    timeline: Dict[str, List[float]] = defaultdict(list)

    if not inquiries.empty:
        for _, inq in inquiries.iterrows():
            inq_num = str(inq.get("شماره استعلام", ""))
            warehouse = str(inq.get("انبار") or "نامشخص")
            product = str(inq.get("شماره درخواست خرید") or inq_num)
            t_inq = inq.get("تاریخ استعلام") or inq.get("created_at")
            t_recv = inq.get("تاریخ دریافت")

            d = _days_between(t_inq, t_recv)
            if d is not None:
                stage_avgs["درخواست تا دریافت"].append(d)
                by_warehouse[warehouse]["درخواست تا دریافت"].append(d)
                by_product[product]["درخواست تا دریافت"].append(d)
                key = _period_key(t_inq, period)
                if key:
                    timeline[key].append(d)

            if not pre_df.empty:
                pis = pre_df[pre_df["شماره استعلام"].astype(str) == inq_num]
                for _, pi in pis.iterrows():
                    t_review = pi.get("تاریخ بررسی")
                    d2 = _days_between(t_inq, t_review)
                    if d2 is not None:
                        stage_avgs["استعلام تا بررسی مدیر"].append(d2)
                        by_warehouse[warehouse]["استعلام تا بررسی مدیر"].append(d2)

    if not orders.empty:
        for _, ord_row in orders.iterrows():
            warehouse = str(ord_row.get("انبار") or "نامشخص")
            product = str(ord_row.get("عنوان کالا") or ord_row.get("شماره خرید") or "—")
            pairs = [
                ("دستور تا سفارش", ord_row.get("تاریخ دستور"), ord_row.get("تاریخ سفارش")),
                ("سفارش تا ثبت پرداخت", ord_row.get("تاریخ سفارش"), ord_row.get("تاریخ ثبت پرداخت")),
                ("ثبت پرداخت تا واریز", ord_row.get("تاریخ ثبت پرداخت"), ord_row.get("تاریخ واریز")),
                ("واریز تا تحویل", ord_row.get("تاریخ واریز"), ord_row.get("تاریخ تحویل")),
            ]
            for label, t1, t2 in pairs:
                d = _days_between(t1, t2)
                if d is not None:
                    stage_avgs[label].append(d)
                    by_warehouse[warehouse][label].append(d)
                    by_product[product][label].append(d)
                    key = _period_key(t1, period)
                    if key:
                        timeline[key].append(d)

    def _avg(lst: List[float]) -> float:
        return round(sum(lst) / len(lst), 1) if lst else 0

    summary = {k: {"avg_days": _avg(v), "count": len(v)} for k, v in stage_avgs.items()}
    warehouses = {
        wh: {st: {"avg_days": _avg(vals), "count": len(vals)} for st, vals in stages.items()}
        for wh, stages in by_warehouse.items()
    }
    products = sorted(
        [
            {"product": p, "stages": {st: {"avg_days": _avg(vals), "count": len(vals)} for st, vals in stg.items()},
             "total_avg": _avg([x for vals in stg.values() for x in vals])}
            for p, stg in by_product.items()
        ],
        key=lambda x: -x["total_avg"],
    )[:50]

    trend = {k: _avg(v) for k, v in sorted(timeline.items())}

    return {
        "period": period,
        "summary": summary,
        "by_warehouse": warehouses,
        "by_product": products,
        "trend": trend,
        "unit": DURATION_UNIT,
        "unit_note": DURATION_UNIT_NOTE,
    }


DURATION_UNIT = "روز"
DURATION_UNIT_NOTE = (
    "روز تقویمی — میانگین فاصله بین دو تاریخ ثبت‌شده در پنل "
    "(استعلام، بررسی مدیر، دستور، سفارش، پرداخت، تحویل)"
)


def _collect_expert_names() -> List[str]:
    from config import PURCHASE_EXPERTS

    names: set = set(PURCHASE_EXPERTS)
    try:
        from services import expert_service

        for n in expert_service.get_active_expert_names() or []:
            s = str(n).strip()
            if s:
                names.add(s)
    except Exception:
        pass

    inquiries = local_storage.get_issued_inquiries()
    if not inquiries.empty and "کارشناس خرید" in inquiries.columns:
        for val in inquiries["کارشناس خرید"].dropna().unique():
            s = str(val).strip()
            if s:
                names.add(s)

    orders = local_storage.get_orders()
    if not orders.empty and "کارشناس" in orders.columns:
        for val in orders["کارشناس"].dropna().unique():
            s = str(val).strip()
            if s:
                names.add(s)

    return sorted(names, key=lambda x: x or "")


def get_all_experts_stage_summary() -> List[Dict]:
    """میانگین مدت مراحل برای همه کارشناسان — برای مقایسه در داشبورد مدیر."""
    rows: List[Dict] = []
    for name in _collect_expert_names():
        tl = get_expert_stage_timeline(name, limit=0)
        stages = tl.get("stages") or []
        total_samples = sum(int(s.get("count") or 0) for s in stages)
        weighted = sum(float(s.get("avg_days") or 0) * int(s.get("count") or 0) for s in stages)
        rows.append({
            "expert": name,
            "stages": stages,
            "has_data": bool(stages),
            "sample_count": total_samples,
            "overall_avg_days": round(weighted / total_samples, 1) if total_samples else 0,
        })
    rows.sort(key=lambda r: (-r["sample_count"], r["expert"]))
    return rows


def _expert_matches_name(expert: str, *values: Any) -> bool:
    if not expert:
        return False
    expert = str(expert).strip()
    for val in values:
        if expert in str(val or ""):
            return True
    return False


def get_expert_stage_timeline(expert: str, limit: int = 12) -> Dict:
    """میانگین مدت مراحل فقط برای موارد ارجاع‌شده به کارشناس."""
    if not expert:
        return {"stages": [], "items": [], "trend": {}}

    inquiries = local_storage.get_issued_inquiries()
    orders = local_storage.get_orders()
    pre_df = local_storage.get_pre_invoices()
    lines_df = local_storage.get_pre_invoice_lines()

    stage_avgs: Dict[str, List[float]] = defaultdict(list)
    items: List[Dict] = []

    expert_inq_nums: set = set()
    if not inquiries.empty:
        for _, inq in inquiries.iterrows():
            if not _expert_matches_name(
                expert,
                inq.get("کارشناس خرید"),
                inq.get("صادر کننده سند"),
                inq.get("created_by"),
            ):
                continue
            inq_num = str(inq.get("شماره استعلام", ""))
            expert_inq_nums.add(inq_num)
            warehouse = str(inq.get("انبار") or "—")
            purchase = str(inq.get("شماره درخواست خرید") or "—")
            t_inq = inq.get("تاریخ استعلام") or inq.get("created_at")
            t_recv = inq.get("تاریخ دریافت")

            d_recv = _days_between(t_recv, t_inq)
            if d_recv is not None:
                stage_avgs["دریافت تا استعلام"].append(d_recv)

            if not pre_df.empty:
                pis = pre_df[pre_df["شماره استعلام"].astype(str) == inq_num]
                for _, pi in pis.iterrows():
                    d_rev = _days_between(t_inq, pi.get("تاریخ بررسی"))
                    if d_rev is not None:
                        stage_avgs["استعلام تا بررسی مدیر"].append(d_rev)

            items.append({
                "type": "استعلام",
                "ref": inq_num,
                "title": f"خرید {purchase}",
                "warehouse": warehouse,
                "date": str(t_inq or "")[:10],
                "status": str(inq.get("وضعیت") or "—"),
            })

    if not orders.empty:
        for _, ord_row in orders.iterrows():
            ord_expert = str(ord_row.get("کارشناس") or "")
            inq_num = str(ord_row.get("شماره استعلام") or "")
            is_mine = _expert_matches_name(expert, ord_expert) or inq_num in expert_inq_nums
            if not is_mine and not lines_df.empty and "شماره دستور" in lines_df.columns:
                order_num = str(ord_row.get("شماره دستور") or "")
                lm = lines_df[lines_df["شماره دستور"].astype(str) == order_num]
                for _, ln in lm.iterrows():
                    if _expert_matches_name(expert, ln.get("کارشناس ارجاع")):
                        is_mine = True
                        break
            if not is_mine:
                continue

            pairs = [
                ("دستور تا سفارش", ord_row.get("تاریخ دستور"), ord_row.get("تاریخ سفارش")),
                ("سفارش تا ثبت پرداخت", ord_row.get("تاریخ سفارش"), ord_row.get("تاریخ ثبت پرداخت")),
                ("ثبت پرداخت تا واریز", ord_row.get("تاریخ ثبت پرداخت"), ord_row.get("تاریخ واریز")),
                ("واریز تا تحویل", ord_row.get("تاریخ واریز"), ord_row.get("تاریخ تحویل")),
            ]
            for label, t1, t2 in pairs:
                d = _days_between(t1, t2)
                if d is not None:
                    stage_avgs[label].append(d)

            items.append({
                "type": "دستور",
                "ref": str(ord_row.get("شماره دستور") or "—"),
                "title": str(ord_row.get("عنوان کالا") or ord_row.get("شماره خرید") or "—"),
                "warehouse": str(ord_row.get("انبار") or "—"),
                "date": str(ord_row.get("تاریخ دستور") or "")[:16],
                "status": str(ord_row.get("مرحله فعلی") or ord_row.get("وضعیت") or "—"),
            })

    def _avg(lst: List[float]) -> float:
        return round(sum(lst) / len(lst), 1) if lst else 0

    stages = [
        {
            "stage": name,
            "avg_days": _avg(vals),
            "count": len(vals),
        }
        for name, vals in stage_avgs.items()
        if vals
    ]
    stages.sort(key=lambda x: -x["count"])

    trend: Dict[str, List[float]] = defaultdict(list)
    for it in items[-30:]:
        key = str(it.get("date") or "")[:7]
        if key:
            trend[key].append(1)
    trend_avg = {k: len(v) for k, v in sorted(trend.items())}

    return {
        "expert": expert,
        "stages": stages,
        "items": items[:limit],
        "item_count": len(items),
        "trend": trend_avg,
        "unit": DURATION_UNIT,
        "unit_note": DURATION_UNIT_NOTE,
    }


def get_expert_dashboard(expert: str) -> Dict:
    """داشبورد کارشناس — فقط داده‌های محلی (استعلام، دستور، تحویل)."""
    from services import kpi_service

    timeline = get_expert_stage_timeline(expert)
    kpis = kpi_service.get_kpis(expert=expert, include_experts=False)

    inquiries = local_storage.get_issued_inquiries()
    orders = local_storage.get_orders()

    inq_status: Dict[str, int] = defaultdict(int)
    if not inquiries.empty:
        for _, row in inquiries.iterrows():
            if not _expert_matches_name(
                expert,
                row.get("کارشناس خرید"),
                row.get("صادر کننده سند"),
                row.get("created_by"),
            ):
                continue
            st = str(row.get("وضعیت") or "در انتظار").strip() or "در انتظار"
            inq_status[st] += 1

    ord_status: Dict[str, int] = defaultdict(int)
    if not orders.empty:
        for _, row in orders.iterrows():
            if not _expert_matches_name(expert, row.get("کارشناس")):
                continue
            st = str(row.get("مرحله فعلی") or row.get("وضعیت") or "دستور خرید").strip()
            ord_status[st] += 1

    item_count = int(timeline.get("item_count") or 0)
    inq_total = sum(inq_status.values())
    closed_orders = sum(
        v for k, v in ord_status.items()
        if "تحویل" in k or "بسته" in k or "پایان" in k
    )
    pending_inq = sum(
        v for k, v in inq_status.items()
        if "انتظار" in k or "بررسی" in k
    )

    stats = {
        "total": item_count,
        "purchase": inq_total,
        "inquiry": inq_total,
        "returned": sum(v for k, v in inq_status.items() if "رد" in k or "معلق" in k),
        "closed": closed_orders,
        "in_progress": pending_inq + sum(
            v for k, v in ord_status.items()
            if k and "تحویل" not in k and "بسته" not in k
        ),
        "by_status": dict(inq_status) if inq_status else dict(ord_status),
        "by_expert": {},
        "by_type": {},
        "by_flow_status": dict(ord_status),
    }

    summary = {
        "total_amount_items": item_count,
        "status_breakdown": dict(inq_status) if inq_status else dict(ord_status),
        "purchase_type_breakdown": {},
        "urgency_breakdown": {},
        "monthly_trend": timeline.get("trend") or {},
    }

    return {
        "stats": stats,
        "summary": summary,
        "kpis": kpis,
        "expert_timeline": timeline,
    }