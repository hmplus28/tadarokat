"""اعتبارسنجی داده‌های اکسل در مقابل پنل"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from django.conf import settings

from purchases.models import Purchase, is_valid_value
from inquiries.models import Inquiry
from orders.models import Order
from deliveries.models import Delivery
from services.excel_importer import ExcelImporter


COMPARE_FIELDS = [
    ('purchase_number', 'شماره درخواست خرید'),
    ('product_title', 'نام قلم خریدنی'),
    ('quantity', 'مقدار درخواست'),
    ('expert_name', 'نام کارشناس خرید'),
    ('inquiry_number', 'شماره استعلام'),
    ('order_number', 'شماره دستور خرید'),
    ('order_request_number', 'شماره سفارش'),
    ('delivery_number', 'شماره تحویل'),
    ('payment_request_number', 'شماره درخواست پرداخت'),
]

STATUS_TO_MENU = {
    'waiting_inquiry': ('purchases', 'درخواست‌های خرید'),
    'inquiry_issued': ('inquiries', 'استعلام‌ها'),
    'order_issued': ('orders', 'دستورات خرید'),
    'order_placed': ('orders', 'دستورات خرید'),
    'waiting_payment': ('orders', 'دستورات خرید'),
    'paid': ('orders', 'دستورات خرید'),
    'delivered': ('deliveries', 'تحویل‌ها'),
}


@dataclass
class FieldCheck:
    field: str
    label: str
    excel_value: str
    db_value: str
    match: bool


@dataclass
class MenuPlacement:
    section: str
    section_label: str
    expected: bool
    found: bool
    detail: str = ''


@dataclass
class RowValidation:
    excel_row: int
    purchase_number: str
    line_number: int
    product_title: str
    found_in_db: bool
    purchase_pk: Optional[int] = None
    field_checks: List[FieldCheck] = field(default_factory=list)
    expected_status: str = ''
    actual_status: str = ''
    status_ok: bool = False
    menu_placements: List[MenuPlacement] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    ok: bool = False


def _normalize_compare(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    if hasattr(val, 'quantize'):
        s = str(val)
        if s.endswith('.00'):
            s = s[:-3]
        elif '.' in s:
            s = str(float(val))
            if s.endswith('.0'):
                s = s[:-2]
        return s.strip()
    cleaned = ExcelImporter.clean_value(val)
    if cleaned is None:
        return ''
    return cleaned.strip()


def _find_excel_path() -> Optional[Path]:
    from services.excel_file_utils import get_input_excel_path

    candidates = [get_input_excel_path()]
    for path in candidates:
        if path.exists() and not path.name.startswith('~$'):
            return path
    return None


def _build_line_numbers(df: pd.DataFrame) -> Dict[int, tuple]:
    """نگاشت index اکسل به (purchase_number, line_number)"""
    line_counters: Dict[str, int] = {}
    mapping = {}
    for idx, row in df.iterrows():
        purchase_number = ExcelImporter.clean_value(row.get('purchase_number'))
        if not purchase_number:
            continue
        line_counters[purchase_number] = line_counters.get(purchase_number, 0) + 1
        mapping[idx] = (purchase_number, line_counters[purchase_number])
    return mapping


def _expected_menu_placements(purchase: Purchase) -> List[MenuPlacement]:
    status = purchase.current_status
    placements = []

    expects_inquiry = is_valid_value(purchase.inquiry_number)
    expects_order = is_valid_value(purchase.order_number)
    expects_delivery = is_valid_value(purchase.delivery_number)

    has_inquiry = bool(
        expects_inquiry
        and Inquiry.objects.filter(inquiry_number=purchase.inquiry_number).exists()
    )
    has_order = bool(
        expects_order
        and Order.objects.filter(order_number=purchase.order_number).exists()
    )
    has_delivery = bool(
        expects_delivery
        and Delivery.objects.filter(delivery_number=purchase.delivery_number).exists()
    )

    placements.append(MenuPlacement(
        section='inquiries',
        section_label='استعلام‌ها',
        expected=expects_inquiry,
        found=has_inquiry,
        detail=f'inquiry_number={purchase.inquiry_number or "—"}',
    ))
    placements.append(MenuPlacement(
        section='orders',
        section_label='دستورات خرید',
        expected=expects_order,
        found=has_order,
        detail=f'order_number={purchase.order_number or "—"}',
    ))
    placements.append(MenuPlacement(
        section='deliveries',
        section_label='تحویل‌ها',
        expected=expects_delivery,
        found=has_delivery,
        detail=f'delivery_number={purchase.delivery_number or "—"}',
    ))

    menu_key, menu_label = STATUS_TO_MENU.get(status, ('purchases', 'درخواست‌های خرید'))
    placements.insert(0, MenuPlacement(
        section=menu_key,
        section_label=f'بخش اصلی: {menu_label}',
        expected=True,
        found=True,
        detail=f'وضعیت: {purchase.current_status_fa}',
    ))
    return placements


def validate_random_rows(sample_size: int = 10, seed: int = 42) -> Dict:
    """مقایسه n ردیف تصادفی اکسل با دیتابیس"""
    file_path = _find_excel_path()
    if not file_path:
        return {'error': 'فایل اکسل یافت نشد', 'rows': []}

    df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
    df = ExcelImporter.normalize_columns(df)
    df = ExcelImporter.map_columns(df)

    line_map = _build_line_numbers(df)
    valid_indices = list(line_map.keys())
    if not valid_indices:
        return {'error': 'ردیف معتبری در اکسل نیست', 'rows': []}

    rng = random.Random(seed)
    chosen = rng.sample(valid_indices, min(sample_size, len(valid_indices)))

    results: List[RowValidation] = []
    for idx in sorted(chosen):
        purchase_number, line_number = line_map[idx]
        row = df.loc[idx]
        result = RowValidation(
            excel_row=int(idx) + 2,
            purchase_number=purchase_number,
            line_number=line_number,
            product_title=_normalize_compare(row.get('product_title', '')),
            found_in_db=False,
        )

        purchase = Purchase.objects.filter(
            purchase_number=purchase_number,
            line_number=line_number,
        ).first()

        if not purchase:
            result.found_in_db = False
            result.issues.append('رکورد در دیتابیس یافت نشد')
            results.append(result)
            continue

        result.found_in_db = True
        result.purchase_pk = purchase.pk

        for field_name, label in COMPARE_FIELDS:
            excel_raw = row.get(field_name) if field_name in row.index else None
            excel_val = _normalize_compare(excel_raw)
            db_val = _normalize_compare(getattr(purchase, field_name, ''))
            match = excel_val == db_val
            if not match and field_name in ExcelImporter.WORKFLOW_FIELDS:
                if excel_val and not db_val:
                    match = True
            result.field_checks.append(FieldCheck(
                field=field_name,
                label=label,
                excel_value=excel_val or '—',
                db_value=db_val or '—',
                match=match,
            ))
            if not match:
                result.issues.append(f'{label}: اکسل="{excel_val or "—"}" ≠ پنل="{db_val or "—"}"')

        expected_status = purchase.calculate_current_status()
        result.expected_status = expected_status
        result.actual_status = purchase.current_status
        result.status_ok = expected_status == purchase.current_status
        if not result.status_ok:
            result.issues.append(
                f'وضعیت: محاسبه‌شده={expected_status} ≠ ذخیره‌شده={purchase.current_status}'
            )

        result.menu_placements = _expected_menu_placements(purchase)
        for mp in result.menu_placements[1:]:
            if mp.expected and not mp.found:
                result.issues.append(f'در منوی «{mp.section_label}» یافت نشد ({mp.detail})')

        result.ok = result.found_in_db and not result.issues
        results.append(result)

    passed = sum(1 for r in results if r.ok)
    return {
        'file_path': str(file_path),
        'total_excel_rows': len(df),
        'sample_size': len(results),
        'passed': passed,
        'failed': len(results) - passed,
        'rows': results,
    }