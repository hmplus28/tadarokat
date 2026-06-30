"""تست قوانین تحویل، داشبورد انبار و اعلان‌ها."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.order_stages import (  # noqa: E402
    is_delivery_completed,
    is_workflow_complete,
    order_is_delivered,
)
from services.notification_service import _is_delivery_notification  # noqa: E402


class DeliveryCompletionRulesTest(unittest.TestCase):
    def test_incomplete_without_permit(self):
        record = {"مرحله فعلی": "تحویل", "تاریخ تحویل": "1404/01/15"}
        self.assertFalse(is_delivery_completed(record))
        self.assertFalse(order_is_delivered(record))

    def test_incomplete_without_date(self):
        record = {"مرحله فعلی": "تحویل", "شماره مجوز ورود": "MV-100"}
        self.assertFalse(is_delivery_completed(record))

    def test_complete_with_permit_and_date(self):
        record = {
            "مرحله فعلی": "تحویل",
            "شماره مجوز ورود": "MV-100",
            "تاریخ تحویل": "1404/01/15",
        }
        self.assertTrue(is_delivery_completed(record))
        self.assertTrue(order_is_delivered(record))

    def test_delivery_record_uses_delivery_number_as_permit(self):
        record = {"شماره تحویل": "TH-001", "تاریخ تحویل": "1404/02/01"}
        self.assertTrue(is_delivery_completed(record))

    def test_stage_only_not_complete(self):
        self.assertFalse(is_workflow_complete("تحویل"))
        self.assertFalse(is_workflow_complete("تحویل", {"مرحله فعلی": "تحویل"}))


class WarehouseNotificationFilterTest(unittest.TestCase):
    def test_delivery_notification_types(self):
        self.assertTrue(_is_delivery_notification({"نوع": "delivery_completed"}))
        self.assertTrue(_is_delivery_notification({"نوع": "delivery"}))
        self.assertTrue(_is_delivery_notification({"عنوان": "ثبت تحویل"}))
        self.assertFalse(_is_delivery_notification({"نوع": "order", "عنوان": "بروزرسانی دستور"}))

    def test_sync_creates_notifications_for_warehouse(self):
        from services.notification_service import list_for_user, sync_warehouse_delivery_notifications

        wh = os.environ.get("TEST_WAREHOUSE", "انبار مصرفی")
        username = "anbar"
        try:
            created = sync_warehouse_delivery_notifications(username, wh)
            items = list_for_user(username, delivery_only=True, warehouse=wh)
        except Exception as exc:
            self.skipTest(f"notification sync unavailable: {exc}")
            return
        self.assertGreaterEqual(len(items), 1, "باید حداقل یک اعلان تحویل برای انبار باشد")
        self.assertTrue(all(
            str(n.get("نوع") or "").lower() in ("delivery_completed", "delivery")
            or str(n.get("عنوان") or "") in ("تحویل شده", "ثبت تحویل")
            for n in items
        ))


class WarehouseDashboardLogicTest(unittest.TestCase):
    def test_kpi_cards_exclude_duplicate_delivery_metric(self):
        from services.warehouse_service import get_warehouse_dashboard  # noqa: E402

        wh = os.environ.get("TEST_WAREHOUSE", "انبار مصرفی")
        try:
            data = get_warehouse_dashboard(wh)
        except Exception as exc:
            self.skipTest(f"warehouse data unavailable: {exc}")
            return

        cards = (data.get("kpis") or {}).get("cards") or []
        keys = {c.get("key") for c in cards}
        self.assertNotIn("deliveries", keys, "KPI «ثبت تحویل» نباید جدا از «تحویل‌شده» باشد")
        self.assertIn("delivered", keys)

        delivered_kpi = next(c for c in cards if c.get("key") == "delivered")
        stats_delivered = (data.get("stats") or {}).get("delivered")
        self.assertEqual(delivered_kpi.get("value"), stats_delivered)

    def test_delivered_count_matches_completion_rule(self):
        from services.warehouse_service import get_warehouse_dashboard  # noqa: E402

        wh = os.environ.get("TEST_WAREHOUSE", "انبار مصرفی")
        try:
            data = get_warehouse_dashboard(wh)
        except Exception as exc:
            self.skipTest(f"warehouse data unavailable: {exc}")
            return

        items = data.get("table_items") or []
        expected = sum(1 for it in items if it.get("تحویل_کامل"))
        actual = (data.get("stats") or {}).get("delivered")
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()