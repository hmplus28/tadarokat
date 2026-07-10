from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Warehouse
from notifications.models import Notification
from services.notification_service import NotificationService


class NotificationServiceTest(TestCase):
    def setUp(self):
        self.wh_store, _ = Warehouse.objects.get_or_create(
            name='انبار مصرفی', defaults={'sort_order': 1}
        )
        self.wh_other, _ = Warehouse.objects.get_or_create(
            name='انبار نت', defaults={'sort_order': 2}
        )
        self.admin = User.objects.create_user(
            username='admin1', email='admin1@test.local', password='pass', role='admin'
        )
        self.warehouse = User.objects.create_user(
            username='wh1',
            email='wh1@test.local',
            password='pass',
            role='warehouse',
            assigned_warehouse=self.wh_store,
        )
        self.other_warehouse = User.objects.create_user(
            username='wh2',
            email='wh2@test.local',
            password='pass',
            role='warehouse',
            assigned_warehouse=self.wh_other,
        )

    def test_notify_role_admin_via_manager_alias(self):
        count = NotificationService.notify_role(
            'manager', 'تست', 'پیام تست', 'info', '/'
        )
        self.assertEqual(count, 1)
        self.assertEqual(Notification.objects.filter(user=self.admin).count(), 1)

    def test_notify_warehouse_payment_ready_targets_assigned_warehouse(self):
        from orders.models import Order
        from purchases.models import Purchase

        purchase = Purchase.objects.create(
            purchase_number='9001',
            product_title='کالا',
            quantity=1,
            unit='عدد',
            supply_unit='انبار مصرفی',
        )
        order = Order.objects.create(
            order_number='8001',
            purchase=purchase,
            product_title='کالا',
            quantity=1,
            order_date='1405/04/01',
            stage='payment',
            warehouse='انبار مصرفی',
        )
        count = NotificationService.notify_warehouse_payment_ready(order)
        self.assertEqual(count, 1)
        self.assertTrue(
            Notification.objects.filter(user=self.warehouse, type='order').exists()
        )
        self.assertFalse(
            Notification.objects.filter(user=self.other_warehouse).exists()
        )

    def test_notify_warehouse_goods_request(self):
        from inquiries.models import Inquiry
        from purchases.models import Purchase

        purchase = Purchase.objects.create(
            purchase_number='9002',
            product_title='کالا انبار',
            quantity=2,
            unit='عدد',
            supply_unit='انبار مصرفی',
        )
        inquiry = Inquiry.objects.create(
            inquiry_number='7001',
            purchase=purchase,
            inquiry_date='1405/04/01',
            warehouse='انبار مصرفی',
            supply_unit='انبار مصرفی',
            warehouse_request_number='WR-100',
            warehouse_request_date='1405/04/05',
        )
        count = NotificationService.notify_warehouse_goods_request(inquiry)
        self.assertEqual(count, 1)
        notif = Notification.objects.get(user=self.warehouse)
        self.assertEqual(notif.type, 'inquiry')
        self.assertIn('WR-100', notif.message)

    def test_notify_warehouse_goods_request_skips_without_fields(self):
        from inquiries.models import Inquiry
        from purchases.models import Purchase

        purchase = Purchase.objects.create(
            purchase_number='9003', product_title='کالا', quantity=1, unit='عدد'
        )
        inquiry = Inquiry.objects.create(
            inquiry_number='7002',
            purchase=purchase,
            inquiry_date='1405/04/01',
            warehouse='انبار مصرفی',
        )
        count = NotificationService.notify_warehouse_goods_request(inquiry)
        self.assertEqual(count, 0)

    def test_notify_warehouse_delivery_scheduled(self):
        from orders.models import Order
        from purchases.models import Purchase

        purchase = Purchase.objects.create(
            purchase_number='9004',
            product_title='کالا تحویل',
            quantity=1,
            unit='عدد',
            supply_unit='انبار مصرفی',
        )
        order = Order.objects.create(
            order_number='8002',
            purchase=purchase,
            product_title='کالا تحویل',
            quantity=1,
            order_date='1405/04/01',
            stage='delivered',
            warehouse='انبار مصرفی',
            delivery_number='D-500',
            delivery_date='1405/04/10',
        )
        count = NotificationService.notify_warehouse_delivery_scheduled(order)
        self.assertEqual(count, 1)
        notif = Notification.objects.get(user=self.warehouse)
        self.assertEqual(notif.type, 'delivery')
        self.assertIn('D-500', notif.message)


class NotificationApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='expert1', email='expert1@test.local', password='pass', role='expert'
        )
        Notification.objects.create(
            user=self.user, title='تست', message='پیام', type='info'
        )
        self.client = Client()

    def test_list_api_requires_login(self):
        res = self.client.get(reverse('notifications:list_api'))
        self.assertEqual(res.status_code, 302)

    def test_list_api_returns_notifications(self):
        self.client.login(username='expert1', password='pass')
        res = self.client.get(reverse('notifications:list_api'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(len(data['items']), 1)

    def test_mark_read_api(self):
        self.client.login(username='expert1', password='pass')
        res = self.client.post(reverse('notifications:mark_read_api'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 0)