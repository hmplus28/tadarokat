from django.test import TestCase

from purchases.models import Purchase
from services.search_service import SearchService


class SearchServiceTest(TestCase):
    def setUp(self):
        Purchase.objects.create(
            purchase_number='7001',
            line_number=1,
            product_title='کالای الف',
            quantity=1,
            unit='عدد',
            order_request_number='ORD-900',
        )
        Purchase.objects.create(
            purchase_number='7002',
            line_number=1,
            product_title='کالای ب',
            quantity=1,
            unit='عدد',
        )

    def test_search_by_purchase_number(self):
        qs = SearchService.filter_purchases(Purchase.objects.all(), '7001')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().purchase_number, '7001')

    def test_search_by_order_request_number(self):
        qs = SearchService.filter_purchases(Purchase.objects.all(), 'ORD-900')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().order_request_number, 'ORD-900')