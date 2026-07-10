"""تحلیل مدت زمان مراحل گردش کار خرید"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from purchases.models import Purchase, is_valid_value, is_real_date

try:
    import jdatetime
except ImportError:
    jdatetime = None


# (key, label, start_field, end_field, prerequisite)
STAGE_DEFINITIONS: List[Tuple[str, str, str, str, str]] = [
    (
        'request_to_inquiry',
        'از تاریخ درخواست (D) تا دریافت درخواست (S)',
        'purchase_date',
        'inquiry_received_date',
        'inquiry_number',
    ),
    (
        'inquiry_to_order',
        'از دریافت درخواست (S) تا دستور خرید (Y)',
        'inquiry_received_date',
        'order_date',
        'order_number',
    ),
    (
        'order_to_placed',
        'از دستور خرید (Y) تا ثبت سفارش (AB)',
        'order_date',
        'order_request_date',
        'order_request_number',
    ),
    (
        'procurement_completion',
        'تکمیل فرایند تدارکات: از دریافت درخواست (S) تا ثبت سفارش (AB)',
        'inquiry_received_date',
        'order_request_date',
        'order_request_number',
    ),
    (
        'placed_to_payment',
        'از ثبت سفارش (AB) تا ثبت واریزی (AP)',
        'order_request_date',
        'payment_registration_date',
        'payment_request_number',
    ),
    (
        'payment_processing',
        'از ثبت واریزی (AP) تا انجام واریزی (AQ)',
        'payment_registration_date',
        'payment_completion_date',
        'payment_request_number',
    ),
    (
        'payment_to_delivery',
        'از انجام واریزی (AQ) تا تحویل (AH)',
        'payment_completion_date',
        'delivery_date',
        'delivery_number',
    ),
    (
        'total_cycle',
        'کل چرخه: از تاریخ درخواست (D) تا تحویل (AH)',
        'purchase_date',
        'delivery_date',
        'delivery_number',
    ),
]

STAGE_SHORT_LABELS = {
    'request_to_inquiry': 'D←S',
    'inquiry_to_order': 'S←Y',
    'order_to_placed': 'Y←AB',
    'procurement_completion': 'S←AB',
    'placed_to_payment': 'AB←AP',
    'payment_processing': 'AP←AQ',
    'payment_to_delivery': 'AQ←AH',
    'total_cycle': 'D←AH',
}


@dataclass
class StageAverage:
    key: str
    label: str
    avg_days: Optional[float]
    median_days: Optional[float]
    sample_count: int


def parse_jalali_date(value) -> Optional['jdatetime.date']:
    """تبدیل رشته تاریخ شمسی به jdatetime.date"""
    if not value or not is_real_date(value):
        return None
    if jdatetime is None:
        return None

    s = str(value).strip().replace('-', '/')
    parts = [p.strip() for p in s.split('/') if p.strip()]
    if len(parts) < 2:
        return None

    try:
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2]) if len(parts) > 2 else 1
        if year < 100:
            year += 1400
        return jdatetime.date(year, month, day)
    except (ValueError, TypeError):
        return None


def days_between(start, end) -> Optional[int]:
    start_date = parse_jalali_date(start)
    end_date = parse_jalali_date(end)
    if not start_date or not end_date:
        return None
    delta = (end_date - start_date).days
    return delta if delta >= 0 else None


def _get_field(purchase: Purchase, field_name: str):
    return getattr(purchase, field_name, None)


def _stage_prerequisite_ok(purchase: Purchase, prerequisite_field: str) -> bool:
    val = _get_field(purchase, prerequisite_field)
    if prerequisite_field.endswith('_date'):
        return is_real_date(val)
    return is_valid_value(val)


def _resolve_stage_values(purchase: Purchase, key: str, start_field: str, end_field: str):
    start_val = _get_field(purchase, start_field)
    end_val = _get_field(purchase, end_field)

    if key == 'placed_to_payment' and not is_real_date(end_val):
        end_val = _get_field(purchase, 'payment_completion_date')

    if key == 'payment_to_delivery':
        if not is_real_date(start_val):
            start_val = _get_field(purchase, 'payment_registration_date')
        if not is_real_date(end_val):
            end_val = _get_field(purchase, 'delivery_date')

    if key == 'payment_processing':
        if not is_real_date(start_val):
            start_val = _get_field(purchase, 'payment_registration_date')
        if not is_real_date(end_val):
            end_val = _get_field(purchase, 'payment_completion_date')

    return start_val, end_val


def compute_purchase_durations(purchase: Purchase) -> Dict[str, Optional[int]]:
    """محاسبه مدت هر مرحله برای یک خرید (بر حسب روز)"""
    result = {}
    for key, _label, start_field, end_field, prerequisite in STAGE_DEFINITIONS:
        if not _stage_prerequisite_ok(purchase, prerequisite):
            result[key] = None
            continue
        start_val, end_val = _resolve_stage_values(purchase, key, start_field, end_field)
        result[key] = days_between(start_val, end_val)
    return result


def _aggregate(values: List[int]) -> tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    values = sorted(values)
    avg = round(sum(values) / len(values), 1)
    mid = len(values) // 2
    if len(values) % 2:
        median = float(values[mid])
    else:
        median = round((values[mid - 1] + values[mid]) / 2, 1)
    return avg, median


def aggregate_stage_averages(purchases) -> List[StageAverage]:
    """میانگین مدت مراحل روی مجموعه خریدها"""
    buckets: Dict[str, List[int]] = {key: [] for key, *_ in STAGE_DEFINITIONS}

    for purchase in purchases.iterator():
        durations = compute_purchase_durations(purchase)
        for key, days in durations.items():
            if days is not None:
                buckets[key].append(days)

    results = []
    for key, label, *_ in STAGE_DEFINITIONS:
        avg, median = _aggregate(buckets[key])
        results.append(StageAverage(
            key=key,
            label=label,
            avg_days=avg,
            median_days=median,
            sample_count=len(buckets[key]),
        ))
    return results


def aggregate_expert_stage_averages(purchases) -> List[Dict]:
    """میانگین مدت مراحل به تفکیک کارشناس"""
    expert_data: Dict[str, Dict[str, List[int]]] = {}

    for purchase in purchases.exclude(expert_name='').iterator():
        expert = purchase.expert_name.strip()
        if not expert:
            continue
        if expert not in expert_data:
            expert_data[expert] = {key: [] for key, *_ in STAGE_DEFINITIONS}

        durations = compute_purchase_durations(purchase)
        for key, days in durations.items():
            if days is not None:
                expert_data[expert][key].append(days)

    rows = []
    for expert, buckets in expert_data.items():
        row = {'expert_name': expert, 'stages': {}, 'total_samples': 0}
        max_samples = 0
        for key, label, *_ in STAGE_DEFINITIONS:
            avg, median = _aggregate(buckets[key])
            row['stages'][key] = {
                'label': label,
                'short_label': STAGE_SHORT_LABELS.get(key, ''),
                'avg_days': avg,
                'median_days': median,
                'sample_count': len(buckets[key]),
            }
            max_samples = max(max_samples, len(buckets[key]))
        row['total_samples'] = max_samples
        rows.append(row)

    rows.sort(key=lambda r: r['total_samples'], reverse=True)
    return rows