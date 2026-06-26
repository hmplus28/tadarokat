"""کنترل دسترسی نقش‌ها به داده‌های گردش کار."""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import HTTPException, status

from config import MANAGER_ROLES
from services.warehouse_resolver import resolve_warehouse_from_delivery, resolve_warehouse_from_order, warehouses_match


def _expert_name(user: dict) -> str:
    return str(user.get("expert") or user.get("name") or "").strip()


def assert_manager(user: dict, detail: str = "فقط مدیر دسترسی دارد") -> None:
    if user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def assert_expert(user: dict, detail: str = "فقط کارشناس دسترسی دارد") -> None:
    if user.get("role") != "expert":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def assert_expert_owns_order(order: Optional[Dict], user: dict) -> None:
    if user.get("role") != "expert":
        return
    expert = _expert_name(user)
    if not expert:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="کارشناس مرتبط یافت نشد")
    order_expert = str((order or {}).get("کارشناس") or "")
    if expert not in order_expert:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی به این دستور مجاز نیست")


def assert_expert_owns_delivery(delivery: Optional[Dict], user: dict) -> None:
    if user.get("role") != "expert":
        return
    from services import local_storage

    order = None
    order_num = str((delivery or {}).get("شماره دستور") or "").strip()
    if order_num:
        order = local_storage.find_order_by_number(order_num)
    if order:
        assert_expert_owns_order(order, user)
        return
    expert = _expert_name(user)
    pn = str((delivery or {}).get("شماره خرید") or "").strip()
    if pn:
        from services.excel_service import _get_merged_purchases, _normalize_id

        purchases = _get_merged_purchases()
        if not purchases.empty and "شماره" in purchases.columns:
            m = purchases[purchases["شماره"].map(_normalize_id) == _normalize_id(pn)]
            if not m.empty:
                purchase_expert = str(m.iloc[0].get("کارشناس خرید") or "")
                if expert in purchase_expert:
                    return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی به این تحویل مجاز نیست")


def assert_warehouse_owns_order(order: Optional[Dict], user: dict) -> None:
    if user.get("role") != "warehouse":
        return
    wh = str(user.get("warehouse") or "").strip()
    if not warehouses_match(resolve_warehouse_from_order(order), wh):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="این مورد به انبار شما مرتبط نیست")


def delivery_visible_for_user(delivery: Dict, user: dict) -> bool:
    role = user.get("role")
    if role in MANAGER_ROLES or role == "admin":
        return True
    if role == "warehouse":
        return warehouses_match(
            resolve_warehouse_from_delivery(delivery),
            user.get("warehouse"),
        )
    if role == "expert":
        try:
            assert_expert_owns_delivery(delivery, user)
            return True
        except HTTPException:
            return False
    return True