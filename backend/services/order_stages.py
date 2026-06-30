"""تعریف مراحل گردش دستور خرید — فقط فایل محلی، بدون اکسل."""
from typing import Dict, List, Optional

ORDER_STAGE_SEQUENCE: List[str] = [
    "دستور خرید",
    "سفارش",
    "ثبت پرداخت",
    "تبدیل وضعیت پرداخت",
    "تحویل",
]

STAGE_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "سفارش": ["شماره سفارش", "تاریخ سفارش"],
    "ثبت پرداخت": ["شماره پرداخت", "تاریخ ثبت پرداخت"],
    "تبدیل وضعیت پرداخت": ["تاریخ واریز"],
    "تحویل": ["شماره مجوز ورود", "تاریخ تحویل"],
}

STAGE_VIEW_FIELDS: Dict[str, List[str]] = {
    "دستور خرید": ["شماره دستور", "تاریخ دستور", "عنوان کالا", "نام پیمانکار", "کارشناس"],
    "سفارش": ["شماره سفارش", "تاریخ سفارش"],
    "ثبت پرداخت": ["شماره پرداخت", "تاریخ ثبت پرداخت"],
    "تبدیل وضعیت پرداخت": ["تاریخ واریز"],
    "تحویل": ["شماره مجوز ورود", "تاریخ تحویل"],
}

LEGACY_STAGE_MAP = {
    "رسید انبار": "تحویل",
    "بسته شده": "تحویل",
}

ALL_WORKFLOW_FIELDS = sorted({
    f for fields in STAGE_REQUIRED_FIELDS.values() for f in fields
})


def normalize_stage(stage: Optional[str]) -> str:
    s = str(stage or "دستور خرید").strip()
    if s in LEGACY_STAGE_MAP:
        return LEGACY_STAGE_MAP[s]
    if s in ORDER_STAGE_SEQUENCE:
        return s
    return "دستور خرید"


def stage_index(stage: str) -> int:
    return ORDER_STAGE_SEQUENCE.index(normalize_stage(stage))


def next_stage_to_complete(current_stage: str) -> Optional[str]:
    current = normalize_stage(current_stage)
    idx = stage_index(current)
    if idx >= len(ORDER_STAGE_SEQUENCE) - 1:
        return None
    return ORDER_STAGE_SEQUENCE[idx + 1]


def is_delivery_completed(record: Optional[Dict]) -> bool:
    """تحویل واقعی: «شماره مجوز ورود» و «تاریخ تحویل» هر دو ثبت شده باشند."""
    if not isinstance(record, dict):
        return False
    permit = str(record.get("شماره مجوز ورود") or record.get("شماره تحویل") or "").strip()
    delivery_date = str(record.get("تاریخ تحویل") or "").strip()
    return bool(permit and delivery_date)


def is_workflow_complete(current_stage: str, record: Optional[Dict] = None) -> bool:
    if normalize_stage(current_stage) != "تحویل":
        return False
    if record is not None:
        return is_delivery_completed(record)
    return False


def order_is_delivered(order: Optional[Dict]) -> bool:
    if not isinstance(order, dict):
        return False
    return is_workflow_complete(str(order.get("مرحله فعلی") or ""), order)


def locked_fields_for(target_stage: str) -> List[str]:
    """فیلدهای مراحل تکمیل‌شده قبل از مرحله‌ای که الان ثبت می‌شود."""
    target = normalize_stage(target_stage)
    if target not in ORDER_STAGE_SEQUENCE:
        return []
    idx = ORDER_STAGE_SEQUENCE.index(target)
    locked: List[str] = []
    for st in ORDER_STAGE_SEQUENCE[1:idx]:
        locked.extend(STAGE_VIEW_FIELDS.get(st, []))
    return locked


def is_stage_completed(order_stage: str, check_stage: str) -> bool:
    return stage_index(normalize_stage(order_stage)) >= stage_index(normalize_stage(check_stage))


def workflow_meta(current_stage: str, order: Optional[Dict] = None) -> Dict:
    current = normalize_stage(current_stage)
    nxt = next_stage_to_complete(current)
    return {
        "current_stage": current,
        "next_stage": nxt,
        "complete": is_workflow_complete(current, order),
        "stages": ORDER_STAGE_SEQUENCE,
        "stage_fields": STAGE_REQUIRED_FIELDS,
        "view_fields": STAGE_VIEW_FIELDS,
    }