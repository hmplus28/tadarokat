from typing import Dict, List, Set

from services import local_storage
from services.user_service import _load_users


def _expert_display_name(user: dict) -> str:
    return str(user.get("expert") or user.get("name") or "").strip()


def get_active_expert_names() -> List[str]:
    names: List[str] = []
    seen: Set[str] = set()
    for user in _load_users():
        if user.get("role") != "expert":
            continue
        if user.get("active") is False:
            continue
        name = _expert_display_name(user)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return sorted(names)


def _names_from_series(df, *columns: str) -> Set[str]:
    found: Set[str] = set()
    if df is None or df.empty:
        return found
    for col in columns:
        if col not in df.columns:
            continue
        for val in df[col].dropna().astype(str).str.strip().tolist():
            if val and val.lower() not in ("none", "nan", ""):
                found.add(val)
    return found


def get_referenced_expert_names() -> Set[str]:
    names: Set[str] = set()
    names.update(_names_from_series(local_storage.get_issued_inquiries(), "کارشناس خرید", "صادر کننده سند"))
    names.update(_names_from_series(local_storage.get_pre_invoice_lines(), "کارشناس ارجاع"))
    names.update(_names_from_series(local_storage.get_orders(), "کارشناس"))
    return names


def list_experts_for_api() -> Dict:
    active = get_active_expert_names()
    active_set = set(active)
    referenced = get_referenced_expert_names()
    legacy = sorted(referenced - active_set)
    all_names = sorted(active_set | referenced)
    return {
        "active": active,
        "legacy": legacy,
        "items": all_names,
    }


def is_assignable_expert(expert_name: str, existing_name: str = "") -> bool:
    name = str(expert_name or "").strip()
    if not name:
        return False
    existing = str(existing_name or "").strip()
    if existing and name == existing:
        return True
    return name in get_active_expert_names()