from decimal import Decimal

from django.test import TestCase

from purchases.models import Purchase
from services.category_amount_service import CategoryAmountService
from services.order_amount_service import OrderAmountService
from services.product_amount_service import ProductAmountService


class OrderAmountServiceTest(TestCase):
    def _create_line(self, purchase_number, order_no, order_total, category='آی تی'):
        return Purchase.objects.create(
            purchase_number=purchase_number,
            line_number=1,
            product_title='کالا',
            product_code='1001',
            quantity=1,
            unit='عدد',
            order_request_number=order_no,
            order_total=order_total,
            product_category=category,
        )

    def test_same_order_number_counted_once(self):
        self._create_line('100', 'ORD-1', 1_000_000)
        Purchase.objects.create(
            purchase_number='101',
            line_number=1,
            product_title='کالا ۲',
            product_code='1002',
            quantity=1,
            unit='عدد',
            order_request_number='ORD-1',
            order_total=1_000_000,
            product_category='آی تی',
        )

        total = OrderAmountService.sum_unique_amounts(Purchase.objects.all())
        self.assertEqual(total, Decimal('1000000'))

    def test_different_order_numbers_summed(self):
        self._create_line('100', 'ORD-1', 1_000_000)
        self._create_line('101', 'ORD-2', 2_000_000)
        total = OrderAmountService.sum_unique_amounts(Purchase.objects.all())
        self.assertEqual(total, Decimal('3000000'))

    def test_category_amounts_not_inflated(self):
        for i in range(5):
            Purchase.objects.create(
                purchase_number=f'10{i}',
                line_number=1,
                product_title=f'کالا {i}',
                product_code=f'200{i}',
                quantity=1,
                unit='عدد',
                order_request_number='19809',
                order_total=1_102_398_000,
                product_category='عمومی تولید',
            )

        summary = CategoryAmountService.get_summary(Purchase.objects.all())
        self.assertEqual(summary['grand_total'], 1_102_398_000.0)
        cat = next(c for c in summary['categories'] if c['name'] == 'عمومی تولید')
        self.assertEqual(cat['amount'], 1_102_398_000.0)
        self.assertEqual(cat['order_count'], 1)
        self.assertEqual(cat['purchase_count'], 5)

    def test_product_amounts_skip_duplicate_order_total(self):
        for i in range(3):
            Purchase.objects.create(
                purchase_number=f'20{i}',
                line_number=1,
                product_title=f'کالا {i}',
                product_code=f'300{i}',
                quantity=1,
                unit='عدد',
                order_request_number='ORD-X',
                order_total=500_000,
            )

        summary = ProductAmountService.get_summary(Purchase.objects.all())
        self.assertEqual(summary['grand_total'], 500_000.0)
        self.assertEqual(summary['order_based_total'], 500_000.0)
        self.assertEqual(summary['order_lines'], 1)