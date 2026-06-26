from typing import Any, Dict, List, Optional

from services import local_storage


def _str_val(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def log_field_changes(
    entity_type: str,
    entity_id: str,
    username: str,
    updates: Dict[str, Any],
    before: Optional[Dict[str, Any]] = None,
    action: str = "ویرایش",
) -> None:
    before = before or {}
    for field, new_val in updates.items():
        old_val = before.get(field)
        if _str_val(old_val) == _str_val(new_val):
            continue
        local_storage.append_edit_history({
            "نوع موجودیت": entity_type,
            "شناسه": str(entity_id),
            "عملیات": action,
            "فیلد": field,
            "مقدار قبلی": _str_val(old_val) or None,
            "مقدار جدید": _str_val(new_val) or None,
            "کاربر": username,
        })


def log_action(
    entity_type: str,
    entity_id: str,
    username: str,
    action: str,
    note: str = "",
) -> None:
    local_storage.append_edit_history({
        "نوع موجودیت": entity_type,
        "شناسه": str(entity_id),
        "عملیات": action,
        "فیلد": None,
        "مقدار قبلی": None,
        "مقدار جدید": note or None,
        "کاربر": username,
    })


def list_history(
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    entity_type: str = "",
    entity_id: str = "",
    page_cap: int = 200,
) -> Dict:
    return local_storage.paginate_edit_history(
        page=page,
        page_size=page_size,
        search=search,
        entity_type=entity_type,
        entity_id=entity_id,
        page_cap=page_cap,
    )