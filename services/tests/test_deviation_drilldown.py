from django.contrib.auth import get_user_model
from django.test import TestCase

from purchases.models import Purchase
from services.deadline_service import DeadlineService
from services.order_deadline_service import OrderDeadlineService
from services.payment_lead_service import PaymentLeadService

User = get_user_model()


class EffectiveRequestDateTests(TestCase):
    def test_prefers_request_date_over_purchase_date(self):
        purchase = Purchase(
            request_date='1405/01/05',
            purchase_date='1405/01/20',
        )
        self.assertEqual(DeadlineService.get_effective_request_date(purchase), '1405/01/05')
        self.assertEqual(DeadlineService.get_effective_date_source(purchase), 'request_date')

    def test_falls_back_to_purchase_date_when_request_empty(self):
        purchase = Purchase(
            request_date='',
            purchase_date='1405/02/10',
        )
        self.assertEqual(DeadlineService.get_effective_request_date(purchase), '1405/02/10')
        self.assertEqual(DeadlineService.get_effective_date_source(purchase), 'purchase_date')

    def test_evaluate_uses_fallback_date_for_direct_warehouse_request(self):
        from accounts.models import ProductCategory, CategoryDeadlineRule

        cat = ProductCategory.objects.create(name='گروه مستقیم', is_active=True)
        CategoryDeadlineRule.objects.create(
            category=cat,
            allowed_days='5,25',
            is_active=True,
        )
        purchase = Purchase.objects.create(
            purchase_number='W1',
            line_number=1,
            product_category='گروه مستقیم',
            request_date='',
            purchase_date='1405/01/30',
        )
        self.assertTrue(DeadlineService.evaluate_purchase(purchase))


class DeviationDrilldownTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='report_admin',
            email='r@test.com',
            password='pass',
            role='admin',
        )

    def test_request_deviation_filter_by_category_paginates(self):
        Purchase.objects.create(
            purchase_number='D1', line_number=1,
            product_category='گروه الف', purchase_date='1405/01/10',
            deadline_deviated=True,
        )
        Purchase.objects.create(
            purchase_number='D2', line_number=1,
            product_category='گروه ب', purchase_date='1405/01/11',
            deadline_deviated=True,
        )
        rows, total = DeadlineService.get_deviated_cases_page(
            Purchase.objects.all(), 'گروه الف', offset=0, limit=100,
        )
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['purchase_number'], 'D1')

    def test_order_deviation_filter_by_category(self):
        Purchase.objects.create(
            purchase_number='O1', line_number=1,
            product_category='گروه سفارش',
            order_deadline_deviated=True,
            inquiry_deadline='1405/01/01',
            order_request_date='1405/02/01',
        )
        rows, total = OrderDeadlineService.get_deviated_cases_page(
            Purchase.objects.all(), 'گروه سفارش',
        )
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]['purchase_number'], 'O1')

    def test_payment_lead_filter_by_category(self):
        Purchase.objects.create(
            purchase_number='P1', line_number=1,
            product_category='گروه پرداخت',
            payment_lead_deviated=True,
            payment_registration_date='1405/01/01',
            payment_completion_date='1405/01/15',
        )
        rows, total = PaymentLeadService.get_deviated_cases_page(
            Purchase.objects.all(), 'گروه پرداخت',
        )
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]['purchase_number'], 'P1')