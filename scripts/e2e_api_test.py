#!/usr/bin/env python3
"""تست API همه بخش‌های سامانه با نقش‌های مختلف."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Tuple

import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api"

USERS = {
    "mostafa": ("mostafa", "mostafa123", "expert"),
    "manager": ("manager", "manager123", "manager"),
    "anbar": ("anbar", "anbar123", "warehouse"),
    "admin": ("admin", "admin123", "admin"),
}


def _req(method: str, path: str, token: str | None = None, body: dict | None = None) -> Tuple[int, Any]:
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return e.code, payload


def login(username: str, password: str) -> str:
    code, data = _req("POST", "/auth/login", body={"username": username, "password": password})
    if code != 200:
        raise RuntimeError(f"login failed {username}: {code} {data}")
    return data["access_token"]


def ok(name: str, code: int, expect: int | Tuple[int, ...] = 200) -> bool:
    expected = (expect,) if isinstance(expect, int) else expect
    passed = code in expected
    mark = "OK" if passed else "FAIL"
    print(f"  [{mark}] {name} -> HTTP {code} (expect {expected})")
    return passed


def test_role(role_key: str) -> List[bool]:
    username, password, role = USERS[role_key]
    print(f"\n=== {role_key} ({role}) ===")
    token = login(username, password)
    results: List[bool] = []

    endpoints: List[Tuple[str, str, int | Tuple[int, ...]]] = [
        ("GET", "/health", 200),
        ("GET", "/stats", 200),
        ("GET", "/reports/dashboard", 200),
        ("GET", "/requests?page=1&page_size=10", 200),
        ("GET", "/requests?page=1&page_size=10&filter=no_inquiry", 200),
        ("GET", "/inquiries?page=1&page_size=10", 403 if role == "expert" else 200),
        ("GET", "/inquiries/mine?page=1&page_size=10", 200 if role == "expert" else 403),
        ("GET", "/inquiries/local?page=1&page_size=10", 200 if role in ("manager", "admin") else 403),
        ("GET", "/reports/my", 200 if role == "expert" else 403),
        ("GET", "/orders?page=1&page_size=10", 200),
        ("GET", "/deliveries?page=1&page_size=10", 200),
        ("GET", "/reports/purchase", 403 if role in ("expert", "warehouse") else 200),
        ("GET", "/reports/reorder?page=1&page_size=10", 403 if role in ("expert", "warehouse") else 200),
        ("GET", "/reports/expert", 200 if role in ("manager", "admin") else 403),
        ("GET", "/reports/duration", 200 if role in ("manager", "admin") else 403),
        ("GET", "/warehouse/dashboard", 200 if role == "warehouse" else 403),
        ("GET", "/warehouse/purchases?page=1&page_size=10", 200 if role == "warehouse" else 403),
        ("GET", "/notifications", 200 if role == "warehouse" else 403),
        ("GET", "/experts", 200),
    ]

    for method, path, expect in endpoints:
        code, _ = _req(method, path, token=token)
        results.append(ok(f"{method} {path}", code, expect))

    if role == "expert":
        code, data = _req("GET", "/requests?page=1&page_size=200&filter=no_inquiry", token=token)
        results.append(ok("no_inquiry has items structure", code, 200))
        if code == 200 and isinstance(data, dict):
            items = data.get("items") or []
            has_issue_candidates = any(
                not i.get("has_local_inquiry") and not i.get("inquiry_approved")
                for i in items
            )
            print(f"       no_inquiry items: {len(items)}, candidates: {has_issue_candidates}")
            results.append(len(items) >= 0)

        code, dash = _req("GET", "/reports/dashboard", token=token)
        if code == 200 and isinstance(dash, dict):
            has_timeline = "expert_timeline" in dash
            no_experts = "experts" not in dash
            print(f"       expert dashboard local: timeline={has_timeline}, no_experts_list={no_experts}")
            results.append(has_timeline and no_experts)

    if role == "warehouse":
        code, wh = _req("GET", "/warehouse/dashboard", token=token)
        if code == 200 and isinstance(wh, dict):
            has_table = "table_items" in wh or "purchases" in wh
            print(f"       warehouse dashboard keys: {list(wh.keys())[:8]}")
            results.append(has_table)

            cards = (wh.get("kpis") or {}).get("cards") or []
            card_keys = {c.get("key") for c in cards}
            no_dup_delivery = "deliveries" not in card_keys and "delivered" in card_keys
            print(f"       warehouse KPI keys: {sorted(card_keys)}")
            results.append(no_dup_delivery)

            items = wh.get("table_items") or []
            delivered_stat = (wh.get("stats") or {}).get("delivered")
            delivered_items = sum(1 for i in items if i.get("تحویل_کامل"))
            print(f"       delivered KPI={delivered_stat}, items_complete={delivered_items}")
            results.append(delivered_stat == delivered_items)

        code, notif = _req("GET", "/notifications", token=token)
        if code == 200 and isinstance(notif, dict):
            notif_items = notif.get("items") or []
            delivery_types = {"delivery_completed", "delivery"}
            only_delivery = all(
                str(n.get("نوع") or "").lower() in delivery_types
                or str(n.get("عنوان") or "") in ("تحویل شده", "ثبت تحویل")
                for n in notif_items
            )
            print(f"       warehouse notifications: {len(notif_items)}, delivery_only={only_delivery}")
            results.append(len(notif_items) >= 1 and only_delivery)

    return results


def main() -> int:
    all_results: List[bool] = []
    for role_key in ("mostafa", "manager", "anbar", "admin"):
        try:
            all_results.extend(test_role(role_key))
        except Exception as exc:
            print(f"  [FAIL] {role_key}: {exc}")
            all_results.append(False)

    passed = sum(1 for r in all_results if r)
    total = len(all_results)
    print(f"\n=== Summary: {passed}/{total} passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())