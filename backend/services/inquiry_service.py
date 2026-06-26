import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from services import expert_service, local_storage, notification_service
from services.excel_service import get_purchase_request_detail, invalidate_cache
from services.json_util import json_safe


def _today_jalali() -> str:
    try:
        import jdatetime
        return jdatetime.date.today().strftime("%Y/%m/%d")
    except ImportError:
        return datetime.now().strftime("%Y/%m/%d")


def generate_inquiry_number() -> str:
    for _ in range(50):
        num = str(random.randint(100000, 999999))
        if not local_storage.inquiry_exists(num):
            return num
    return str(random.randint(1000000, 9999999))


def _pick_field(detail: Dict, *names: str) -> Any:
    for name in names:
        if name in detail and detail.get(name) not in (None, ""):
            return detail.get(name)
    for key, value in detail.items():
        key_str = str(key).replace("\n", " ").strip()
        for name in names:
            if name in key_str and value not in (None, ""):
                return value
    return None


def _expert_matches(user: dict, assigned_expert: Any) -> bool:
    if user.get("role") in ("admin", "manager"):
        return True
    if user.get("role") != "expert":
        return False
    expert_name = str(user.get("expert") or user.get("name") or "").strip()
    if not expert_name:
        return False
    return expert_name in str(assigned_expert or "")


def _assert_expert_owns_purchase(purchase: Dict, user: dict) -> None:
    if user.get("role") not in ("expert",):
        return
    assigned = purchase.get("کارشناس خرید") or ""
    if not _expert_matches(user, assigned):
        raise ValueError("این درخواست به کارشناس دیگری ارجاع شده است")


def lookup_purchase(purchase_number: str) -> Optional[Dict]:
    detail = get_purchase_request_detail(str(purchase_number))
    if not detail:
        return None
    purchase_lines = detail.get("purchase_lines") or []
    line_count = detail.get("line_count") or len(purchase_lines) or 1
    return {
        "شماره خرید": detail.get("شماره"),
        "شماره مبنا": detail.get("شماره مبنا"),
        "تاریخ درخواست کالا": _pick_field(detail, "تاریخ درخواست کالا"),
        "تاریخ دریافت": _pick_field(detail, "تاریخ دریافت"),
        "عنوان کالا": detail.get("عنوان قلم خریدنی"),
        "کد قلم خریدنی": detail.get("کد قلم خریدنی"),
        "مقدار": detail.get("مقدار"),
        "واحد": detail.get("واحد سنجش قلم خریدنی") or detail.get("واحد"),
        "واحد سنجش قلم خریدنی": detail.get("واحد سنجش قلم خریدنی"),
        "نوع خرید": detail.get("نوع خرید"),
        "کارشناس خرید": detail.get("کارشناس خرید"),
        "مهلت استعلام": detail.get("مهلت استعلام"),
        "واحد/رمز تامین": detail.get("واحد/رمز تامین"),
        "رمز فوریت": detail.get("رمز فوریت"),
        "درخواست کننده": detail.get("درخواست کننده"),
        "توضیحات": detail.get("توضیحات"),
        "شماره استعلام موجود": detail.get("شماره استعلام"),
        "line_count": line_count,
        "purchase_lines": purchase_lines,
    }


def _calc_lines_total(lines: List[Dict]) -> float:
    total = 0.0
    for line in lines:
        qty = float(line.get("تعداد") or 0)
        price = float(line.get("فی") or 0)
        total += float(line.get("جمع کل") or qty * price)
    return total


def create_inquiry_with_preinvoices(payload: Dict, issuer_name: str, username: str, user: Optional[dict] = None) -> Dict:
    purchase_number = str(payload.get("purchase_number", "")).strip()
    if not purchase_number:
        raise ValueError("شماره خرید الزامی است")

    purchase = lookup_purchase(purchase_number)
    if not purchase:
        raise ValueError("درخواست خرید یافت نشد")

    if user:
        _assert_expert_owns_purchase(purchase, user)

    expert_key = str(purchase.get("کارشناس خرید") or issuer_name or "").strip()

    if local_storage.purchase_has_approved_inquiry(purchase_number, expert_key):
        raise ValueError("پس از صدور دستور برای این کارشناس امکان استعلام مجدد وجود ندارد")

    if local_storage.purchase_has_local_inquiry(purchase_number, expert_key):
        existing = local_storage.get_local_inquiry_by_purchase(purchase_number, expert_key)
        raise ValueError(f"این کارشناس قبلاً استعلام {existing} برای این خرید ثبت کرده")

    inquiry_number = str(payload.get("inquiry_number") or generate_inquiry_number())
    if local_storage.inquiry_exists(inquiry_number):
        raise ValueError("شماره استعلام تکراری است")

    pre_invoices = payload.get("pre_invoices") or []
    if not pre_invoices:
        raise ValueError("حداقل یک پیش‌فاکتور پیمانکار الزامی است")

    required_fields = {
        "مهلت استعلام": payload.get("مهلت استعلام") or payload.get("deadline") or purchase.get("مهلت استعلام"),
        "واحد/رمز تامین": payload.get("واحد/رمز تامین") or purchase.get("واحد/رمز تامین"),
        "رمز فوریت": payload.get("رمز فوریت"),
        "انبار": payload.get("انبار"),
        "درخواست دهنده": payload.get("درخواست دهنده") or purchase.get("درخواست کننده"),
        "شماره درخواست کالا": payload.get("شماره درخواست کالا") or purchase.get("شماره مبنا"),
        "تاریخ درخواست کالا": payload.get("تاریخ درخواست کالا") or purchase.get("تاریخ درخواست کالا"),
        "تاریخ دریافت": payload.get("تاریخ دریافت") or purchase.get("تاریخ دریافت"),
    }
    for label, value in required_fields.items():
        if not str(value or "").strip():
            raise ValueError(f"{label} الزامی است")

    today = _today_jalali()
    inquiry_record = {
        "شماره استعلام": inquiry_number,
        "شماره درخواست خرید": purchase_number,
        "نوع خرید": payload.get("نوع خرید") or purchase.get("نوع خرید") or "استعلامی",
        "تاریخ استعلام": payload.get("تاریخ استعلام") or today,
        "وضعیت": "ثبت شده",
        "مهلت استعلام": required_fields["مهلت استعلام"],
        "واحد/رمز تامین": required_fields["واحد/رمز تامین"] or "تدارکات داخلی",
        "رمز فوریت": required_fields["رمز فوریت"],
        "علت خرید": payload.get("علت خرید") or "",
        "انبار": required_fields["انبار"],
        "درخواست دهنده": required_fields["درخواست دهنده"],
        "ریسک عدم خرید": payload.get("ریسک عدم خرید") or "",
        "شماره درخواست کالا": required_fields["شماره درخواست کالا"],
        "تاریخ درخواست کالا": required_fields["تاریخ درخواست کالا"],
        "تاریخ دریافت": required_fields["تاریخ دریافت"],
        "صادر کننده سند": issuer_name,
        "کارشناس خرید": purchase.get("کارشناس خرید") or issuer_name,
    }
    local_storage.append_inquiry(inquiry_record, username)
    from services import history_service
    history_service.log_action("استعلام", inquiry_number, username, "ایجاد", f"خرید {purchase_number}")
    saved_preinvoices = []
    for pi in pre_invoices:
        contractor = str(pi.get("نام پیمانکار") or pi.get("contractor") or "").strip()
        pre_number = str(pi.get("شماره پیش فاکتور") or pi.get("preinvoice_number") or "").strip()
        if not contractor:
            raise ValueError("نام پیمانکار الزامی است")
        if not pre_number:
            raise ValueError("شماره پیش‌فاکتور الزامی است")
        if local_storage.preinvoice_duplicate(inquiry_number, contractor, pre_number):
            raise ValueError(f"پیش‌فاکتور {pre_number} از {contractor} تکراری است")

        lines = pi.get("lines") or pi.get("items") or []
        if not lines:
            lines = [{
                "ردیف": 1,
                "عنوان کالا": pi.get("عنوان کالا") or purchase.get("عنوان کالا"),
                "فی": pi.get("فی", 0),
                "تعداد": pi.get("تعداد") or purchase.get("مقدار") or 1,
                "توضیحات": purchase.get("توضیحات"),
            }]

        lines_total = _calc_lines_total(lines)
        invoice_type = str(pi.get("نوع فاکتور") or pi.get("invoice_type") or "").strip()
        if invoice_type == "رسمی":
            vat_enabled = True
        elif invoice_type == "کد ملی":
            vat_enabled = False
        else:
            vat_enabled = bool(pi.get("اعمال مالیات ده درصد") or pi.get("vat_enabled"))
            invoice_type = "رسمی" if vat_enabled else "کد ملی"
        vat = float(pi.get("مالیات بر ارزش افزوده") or pi.get("vat") or 0)
        if vat_enabled and vat <= 0:
            vat = round(lines_total * 0.1, 2)
        discount = float(pi.get("تخفیف") or pi.get("discount") or 0)
        grand_total = lines_total + vat - discount

        pre_record = local_storage.append_pre_invoice({
            "شماره استعلام": inquiry_number,
            "شماره پیش فاکتور": pre_number,
            "نام پیمانکار": contractor,
            "شهر پیمانکار": pi.get("شهر پیمانکار") or pi.get("contractor_city") or "",
            "اعمال مالیات ده درصد": vat_enabled,
            "نوع فاکتور": invoice_type,
            "شرح": pi.get("شرح") or pi.get("description") or "",
            "تاریخ پیش فاکتور": pi.get("تاریخ پیش فاکتور") or pi.get("date") or today,
            "مالیات بر ارزش افزوده": vat,
            "تخفیف": discount,
            "زمان تحویل": pi.get("زمان تحویل") or pi.get("delivery_time") or "",
            "توضیحات": pi.get("توضیحات") or pi.get("notes") or "",
            "جمع کل": grand_total,
            "انتخاب شده": bool(pi.get("انتخاب شده") or pi.get("selected")),
        }, username)

        saved_lines = local_storage.append_pre_invoice_lines(lines, pre_record["id"])
        saved_preinvoices.append({**pre_record, "lines": saved_lines})

    history_rows = []
    product_code = purchase.get("کد قلم خریدنی")
    for pi_saved in saved_preinvoices:
        for line in pi_saved.get("lines") or []:
            history_rows.append({
                "کد قلم خریدنی": product_code,
                "عنوان کالا": line.get("عنوان کالا"),
                "فی": line.get("فی"),
                "تعداد": line.get("تعداد"),
                "واحد": line.get("واحد"),
                "نام پیمانکار": pi_saved.get("نام پیمانکار"),
                "شهر پیمانکار": pi_saved.get("شهر پیمانکار"),
                "شماره استعلام": inquiry_number,
                "شماره خرید": purchase_number,
                "تاریخ خرید": inquiry_record.get("تاریخ استعلام"),
            })
    local_storage.append_product_history_records(history_rows, username)

    local_storage.save_purchase_edit(str(purchase_number), {
        "شماره استعلام": inquiry_number,
        "مهلت استعلام": inquiry_record["مهلت استعلام"],
        "وضعیت": "در جریان",
    }, username)

    invalidate_cache()
    return {
        "ok": True,
        "inquiry": inquiry_record,
        "pre_invoices": saved_preinvoices,
        "saved_to": str(local_storage.LOCAL_EXCEL_PATH),
    }


def _format_review_datetime(value: Any) -> str:
    if not value:
        return "—"
    text = str(value).strip()
    if not text:
        return "—"
    return text[:16].replace("T", " ").replace("-", "/")


def _is_selected_flag(val: Any) -> bool:
    if val is True:
        return True
    return str(val or "").strip().lower() in ("true", "1", "1.0", "yes")


def _build_approval_summary(inquiry: Dict, pre_list: List[Dict], inquiry_number: str) -> Dict:
    approved_pres = [p for p in pre_list if str(p.get("وضعیت مدیر") or "") == "تایید شده"]
    rejected_pres = [p for p in pre_list if str(p.get("وضعیت مدیر") or "") == "رد شده"]
    pending_pres = [p for p in pre_list if str(p.get("وضعیت مدیر") or "") in ("", "در انتظار", "None", "nan")]

    reviewer = None
    reviewed_at = None
    comment = None
    for pre in approved_pres + rejected_pres:
        if pre.get("بررسی کننده"):
            reviewer = pre.get("بررسی کننده")
            reviewed_at = pre.get("تاریخ بررسی")
            comment = pre.get("کامنت مدیر") or comment
            break

    approved_lines = []
    for pre in pre_list:
        contractor = pre.get("نام پیمانکار") or "—"
        for line in pre.get("lines") or []:
            if not _is_selected_flag(line.get("منتخب مدیر")):
                continue
            approved_lines.append({
                "ردیف": line.get("ردیف"),
                "عنوان کالا": line.get("عنوان کالا"),
                "پیمانکار": contractor,
                "شهر پیمانکار": pre.get("شهر پیمانکار"),
                "فی": line.get("فی"),
                "تعداد": line.get("تعداد"),
                "واحد": line.get("واحد"),
                "جمع کل": line.get("جمع کل"),
                "کارشناس ارجاع": line.get("کارشناس ارجاع"),
                "شماره دستور": line.get("شماره دستور"),
                "وضعیت": line.get("line_status"),
                "has_order": line.get("has_order"),
            })

    orders_df = local_storage.get_orders()
    order_records = []
    if not orders_df.empty:
        omatch = orders_df[orders_df["شماره استعلام"].astype(str) == str(inquiry_number)]
        order_records = [json_safe(r) for r in omatch.to_dict(orient="records")]

    return json_safe({
        "has_manager_decision": bool(approved_lines or approved_pres or rejected_pres),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reviewed_at_display": _format_review_datetime(reviewed_at),
        "comment": comment,
        "approved_line_count": len(approved_lines),
        "approved_lines": approved_lines,
        "approved_contractors": [
            {"نام": p.get("نام پیمانکار"), "شماره پیش فاکتور": p.get("شماره پیش فاکتور"), "جمع کل": p.get("جمع کل")}
            for p in approved_pres
        ],
        "rejected_contractors": [
            {"نام": p.get("نام پیمانکار"), "دلیل": p.get("کامنت مدیر") or "—"}
            for p in rejected_pres
        ],
        "pending_contractors": [p.get("نام پیمانکار") for p in pending_pres],
        "issuer": inquiry.get("صادر کننده سند"),
        "issued_at": inquiry.get("تاریخ استعلام"),
        "inquiry_status": inquiry.get("وضعیت"),
        "orders": order_records,
    })


def get_inquiry_detail(inquiry_number: str) -> Optional[Dict]:
    inq_df = local_storage.get_issued_inquiries()
    if inq_df.empty:
        return None
    inq_match = inq_df[inq_df["شماره استعلام"].astype(str) == str(inquiry_number)]
    if inq_match.empty:
        return None

    inquiry = inq_match.iloc[0].to_dict()
    pre_df = local_storage.get_pre_invoices()
    lines_df = local_storage.get_pre_invoice_lines()

    pre_list = []
    if not pre_df.empty:
        pres = pre_df[pre_df["شماره استعلام"].astype(str) == str(inquiry_number)]
        for _, row in pres.iterrows():
            pre = row.to_dict()
            pre_id = str(pre.get("id", ""))
            if not lines_df.empty:
                pre_lines = lines_df[lines_df["preinvoice_id"].astype(str) == pre_id]
                pre["lines"] = pre_lines.to_dict(orient="records")
            else:
                pre["lines"] = []
            pre_list.append(pre)

    _refresh_inquiry_status(inquiry_number)
    inq_df = local_storage.get_issued_inquiries()
    inq_match = inq_df[inq_df["شماره استعلام"].astype(str) == str(inquiry_number)]
    if not inq_match.empty:
        inquiry["وضعیت"] = inq_match.iloc[0].get("وضعیت")

    order_stats = local_storage.get_inquiry_line_order_stats(inquiry_number)
    for pre in pre_list:
        for line in pre.get("lines") or []:
            lid = str(line.get("id", ""))
            line["has_order"] = local_storage.line_has_order(lid)
            is_selected = _is_selected_flag(line.get("منتخب مدیر"))
            if line["has_order"]:
                line["line_status"] = "دستور صادر"
            elif is_selected:
                line["line_status"] = "در انتظار دستور"
            else:
                line["line_status"] = "—"

    inquiry["pre_invoices"] = [json_safe(p) for p in pre_list]
    inquiry["has_orders"] = local_storage.inquiry_has_orders(inquiry_number)
    inquiry["order_count"] = local_storage.inquiry_order_count(inquiry_number)
    inquiry.update(order_stats)
    pending = order_stats.get("pending_order_lines", 0)
    pending_rows = order_stats.get("pending_row_decisions", 0)
    total_rows = order_stats.get("total_rows", 0)
    ordered_rows = order_stats.get("lines_with_orders", 0)
    inquiry["fully_locked"] = (
        total_rows > 0
        and ordered_rows >= total_rows
        and pending == 0
        and pending_rows == 0
        and inquiry["has_orders"]
    )
    inquiry["locked"] = inquiry["fully_locked"]
    inquiry["partially_approved"] = (
        ordered_rows > 0 and (ordered_rows < total_rows or pending > 0 or pending_rows > 0)
    )
    inquiry["approval_summary"] = _build_approval_summary(inquiry, pre_list, inquiry_number)
    return json_safe(inquiry)


def _user_owns_inquiry(item: dict, user: dict) -> bool:
    if user.get("role") in ("admin", "manager"):
        return True
    if user.get("role") == "warehouse":
        return str(item.get("انبار") or "") == str(user.get("warehouse") or "")
    if user.get("role") != "expert":
        return False
    assigned = item.get("کارشناس خرید") or item.get("صادر کننده سند") or ""
    return _expert_matches(user, assigned)


def get_inquiry_for_user(inquiry_number: str, user: dict) -> Optional[Dict]:
    data = get_inquiry_detail(inquiry_number)
    if not data:
        return None
    if not _user_owns_inquiry(data, user):
        return None
    return data


def _inquiry_search_cols() -> List[str]:
    return [
        "شماره استعلام", "شماره درخواست خرید", "نوع خرید", "انبار",
        "درخواست دهنده", "صادر کننده سند", "کارشناس خرید", "وضعیت",
    ]


def _attach_inquiry_stats(df, pre_df):
    rows = []
    for _, row in df.iterrows():
        item = json_safe(row.to_dict())
        inq_num = str(item.get("شماره استعلام", ""))
        if not pre_df.empty:
            pis = pre_df[pre_df["شماره استعلام"].astype(str) == inq_num]
            cnt = len(pis)
            pending = int((pis["وضعیت مدیر"].astype(str) == "در انتظار").sum())
            approved = int((pis["وضعیت مدیر"].astype(str) == "تایید شده").sum())
            rejected = int((pis["وضعیت مدیر"].astype(str) == "رد شده").sum())
        else:
            cnt, pending, approved, rejected = 0, 0, 0, 0
        item["preinvoice_count"] = cnt
        item["pending_review"] = pending
        item["approved_count"] = approved
        item["rejected_count"] = rejected
        item["inquiry_approved"] = approved > 0
        inq_status = str(item.get("وضعیت", ""))
        if inq_status and inq_status not in ("ثبت شده",):
            item["manager_status"] = inq_status
        elif approved:
            item["manager_status"] = "تایید شده"
        elif rejected and not pending:
            item["manager_status"] = "رد شده"
        elif pending:
            item["manager_status"] = "در انتظار بررسی مدیر"
        else:
            item["manager_status"] = "—"
        item["has_orders"] = local_storage.inquiry_has_orders(inq_num)
        item["order_count"] = local_storage.inquiry_order_count(inq_num)
        item["pending_order_lines"] = local_storage.get_inquiry_line_order_stats(inq_num).get("pending_order_lines", 0)
        if not pre_df.empty:
            inq_pres = pre_df[pre_df["شماره استعلام"].astype(str) == inq_num]
            reviewed = inq_pres[inq_pres["بررسی کننده"].notna() & (inq_pres["بررسی کننده"].astype(str).str.strip() != "")]
            if not reviewed.empty:
                r0 = reviewed.iloc[-1]
                item["manager_reviewer"] = r0.get("بررسی کننده")
                item["manager_reviewed_at"] = _format_review_datetime(r0.get("تاریخ بررسی"))
                item["manager_comment"] = r0.get("کامنت مدیر")
        rows.append(item)
    return rows


def list_local_inquiries(
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    user: Optional[dict] = None,
    expert: str = "",
    status: str = "",
    warehouse: str = "",
    exclude_moved_to_orders: bool = False,
) -> Dict:
    import math

    df = local_storage.get_issued_inquiries()
    if df.empty:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    if user and user.get("role") == "expert":
        import pandas as pd
        expert_name = str(user.get("expert") or user.get("name") or "").strip()
        uname = str(user.get("username") or "").lower()
        if expert_name:
            mask = pd.Series(False, index=df.index)
            if "کارشناس خرید" in df.columns:
                mask = mask | df["کارشناس خرید"].astype(str).str.contains(expert_name, na=False)
            if "صادر کننده سند" in df.columns:
                mask = mask | df["صادر کننده سند"].astype(str).str.contains(expert_name, na=False)
            if "created_by" in df.columns and uname:
                mask = mask | df["created_by"].astype(str).str.lower().eq(uname)
            df = df[mask]
    elif user and user.get("role") == "warehouse" and user.get("warehouse"):
        if "انبار" in df.columns:
            df = df[df["انبار"].astype(str) == str(user["warehouse"])]

    if expert and "کارشناس خرید" in df.columns:
        df = df[df["کارشناس خرید"].astype(str).str.contains(expert.strip(), na=False)]
    elif expert and "صادر کننده سند" in df.columns:
        df = df[df["صادر کننده سند"].astype(str).str.contains(expert.strip(), na=False)]

    if warehouse and "انبار" in df.columns:
        df = df[df["انبار"].astype(str) == str(warehouse).strip()]

    if search:
        import pandas as pd
        q = search.strip().lower()
        cols = [c for c in _inquiry_search_cols() if c in df.columns]
        mask = pd.Series(False, index=df.index)
        for col in cols:
            mask = mask | df[col].astype(str).str.lower().str.contains(q, na=False)
        df = df[mask]

    pre_df = local_storage.get_pre_invoices()
    all_items = _attach_inquiry_stats(df, pre_df)

    if status:
        all_items = [i for i in all_items if i.get("manager_status") == status]

    if exclude_moved_to_orders:
        all_items = [i for i in all_items if not i.get("has_orders")]

    total = len(all_items)
    start = (max(1, page) - 1) * page_size
    items = all_items[start : start + page_size]
    pages = math.ceil(total / page_size) if total else 0
    return json_safe({
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": pages,
    })


def _resolve_line_context(item: Dict) -> Dict:
    preinvoice_id = str(item.get("preinvoice_id") or "").strip()
    line_id = str(item.get("line_id") or "").strip()
    expert = str(item.get("کارشناس") or item.get("expert") or "").strip()
    order_number = str(item.get("شماره دستور") or "").strip()
    defer_order = bool(item.get("defer_order") or item.get("skip_order"))

    if not expert:
        raise ValueError("کارشناس ارجاع برای هر ردیف الزامی است")

    lines_df = local_storage.get_pre_invoice_lines()
    line_row = None
    existing_expert = ""
    if line_id and not lines_df.empty:
        match = lines_df[lines_df["id"].astype(str) == line_id]
        if not match.empty:
            line_row = match.iloc[0].to_dict()
            existing_expert = str(line_row.get("کارشناس ارجاع") or "")
    if not expert_service.is_assignable_expert(expert, existing_expert):
        raise ValueError(f"کارشناس «{expert}» فعال نیست — از لیست کارشناسان فعال انتخاب کنید")

    if not preinvoice_id or not line_id:
        raise ValueError("انتخاب پیمانکار برای هر ردیف الزامی است")

    pre_df = local_storage.get_pre_invoices()
    contractor = ""
    if not pre_df.empty:
        pm = pre_df[pre_df["id"].astype(str) == preinvoice_id]
        if not pm.empty:
            contractor = str(pm.iloc[0].get("نام پیمانکار") or "")

    return {
        "preinvoice_id": preinvoice_id,
        "line_id": line_id,
        "expert": expert,
        "order_number": order_number,
        "defer_order": defer_order,
        "line_row": line_row,
        "contractor": contractor,
    }


def _sync_preinvoice_statuses(inquiry_number: str, selected_preinvoice_ids: set, manager_name: str, comment: str) -> None:
    pre_df = local_storage.get_pre_invoices()
    if pre_df.empty:
        return
    lines_df = local_storage.get_pre_invoice_lines()
    inq_pres = pre_df[pre_df["شماره استعلام"].astype(str) == str(inquiry_number)]
    for _, pi in inq_pres.iterrows():
        pid = str(pi.get("id", ""))
        if pid in selected_preinvoice_ids:
            local_storage.update_pre_invoice_status(pid, "تایید شده", manager_name, comment=comment)
            continue
        has_lines = False
        if not lines_df.empty:
            has_lines = bool((lines_df["preinvoice_id"].astype(str) == pid).any())
        reject_note = "رد — ردیفی انتخاب نشد" if has_lines else "رد — بدون قیمت‌گذاری"
        local_storage.update_pre_invoice_status(pid, "رد شده", manager_name, comment=reject_note)


def _refresh_inquiry_status(inquiry_number: str) -> str:
    stats = local_storage.get_inquiry_line_order_stats(inquiry_number)
    decided = stats.get("selected_lines", 0)
    pending = stats.get("pending_order_lines", 0)
    pending_rows = stats.get("pending_row_decisions", 0)
    total_rows = stats.get("total_rows", 0)
    ordered_rows = stats.get("lines_with_orders", 0)
    has_orders = local_storage.inquiry_has_orders(inquiry_number)

    if decided == 0:
        status = "ثبت شده"
    elif ordered_rows >= total_rows and pending == 0 and pending_rows == 0 and has_orders:
        status = "تایید شده"
    elif has_orders:
        status = "تایید ردیفی — دستور جزئی"
    else:
        status = "تایید ردیفی — در انتظار دستور"

    local_storage.update_inquiry_status(inquiry_number, status)
    return status


def manager_approve_lines(
    inquiry_number: str,
    lines: List[Dict],
    manager_name: str,
    username: str,
    comment: str = "",
    issue_orders: bool = True,
) -> Dict:
    from services import history_service, order_service

    inquiry = get_inquiry_detail(inquiry_number)
    if not inquiry:
        raise ValueError("استعلام یافت نشد")

    if not lines:
        raise ValueError("حداقل یک ردیف کالا باید انتخاب شود")

    created = []
    selected_preinvoice_ids = set()
    saved_count = 0

    for item in lines:
        ctx = _resolve_line_context(item)
        line_id = ctx["line_id"]
        if local_storage.line_has_order(line_id):
            continue

        order_number = ctx["order_number"]
        defer = ctx["defer_order"] or not order_number

        if issue_orders and defer:
            local_storage.update_line_manager_decision(line_id, ctx["expert"], "", selected=True)
            selected_preinvoice_ids.add(ctx["preinvoice_id"])
            saved_count += 1
            continue

        if not issue_orders:
            local_storage.update_line_manager_decision(line_id, ctx["expert"], "", selected=True)
            selected_preinvoice_ids.add(ctx["preinvoice_id"])
            saved_count += 1
            continue

        line_row = ctx["line_row"]
        result = order_service.issue_order({
            "شماره دستور": order_number,
            "شماره استعلام": inquiry_number,
            "preinvoice_id": ctx["preinvoice_id"],
            "line_id": line_id,
            "کارشناس": ctx["expert"],
            "نام پیمانکار": ctx["contractor"],
            "عنوان کالا": line_row.get("عنوان کالا") if line_row else item.get("عنوان کالا"),
            "ردیف": line_row.get("ردیف") if line_row else item.get("ردیف"),
            "واحد": line_row.get("واحد") if line_row else None,
            "فی": line_row.get("فی") if line_row else None,
            "تعداد": line_row.get("تعداد") if line_row else None,
            "توضیحات": comment,
        }, manager_name, username)

        local_storage.update_line_manager_decision(line_id, ctx["expert"], order_number, selected=True)
        selected_preinvoice_ids.add(ctx["preinvoice_id"])
        created.append(result.get("order"))

    if issue_orders and not created:
        raise ValueError("حداقل یک ردیف با شماره دستور (بدون دستور قبلی) لازم است")

    if not issue_orders and saved_count == 0:
        raise ValueError("هیچ ردیف قابل ذخیره‌ای یافت نشد")

    _sync_preinvoice_statuses(inquiry_number, selected_preinvoice_ids, manager_name, comment)
    status = _refresh_inquiry_status(inquiry_number)

    action = "صدور دستور" if issue_orders else "ذخیره تایید ردیفی"
    detail = f"{len(created)} دستور" if issue_orders else f"{saved_count} ردیف"
    history_service.log_action(
        "استعلام", inquiry_number, username, action,
        f"{detail} · {comment or ''}".strip(),
    )
    invalidate_cache()
    return {
        "ok": True,
        "orders": created,
        "count": len(created),
        "saved": saved_count,
        "issue_orders": issue_orders,
        "status": status,
    }


def manager_decision(
    preinvoice_id: str, action: str, reviewer_name: str, username: str, comment: Optional[str] = None
) -> Dict:
    from services import history_service

    status_map = {"approve": "تایید شده", "reject": "رد شده"}
    if action not in status_map:
        raise ValueError("عملیات نامعتبر")
    pre_df = local_storage.get_pre_invoices()
    before = None
    if not pre_df.empty:
        match = pre_df[pre_df["id"].astype(str) == str(preinvoice_id)]
        if not match.empty:
            before = match.iloc[0].to_dict()
    result = local_storage.update_pre_invoice_status(
        preinvoice_id, status_map[action], reviewer_name, comment=comment
    )
    if result:
        inq_num = str(result.get("شماره استعلام") or preinvoice_id)
        history_service.log_action(
            "پیش‌فاکتور",
            inq_num,
            username,
            status_map[action],
            f"پیمانکار {result.get('نام پیمانکار') or '—'} — {comment or ''}".strip(),
        )
    if not result:
        raise ValueError("پیش‌فاکتور یافت نشد")
    invalidate_cache()
    return {"ok": True, "preinvoice": result, "action": action}