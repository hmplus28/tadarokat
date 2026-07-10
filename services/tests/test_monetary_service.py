from decimal import Decimal

from django.test import TestCase

from purchases.models import Purchase
from services.financial_loss_service import FinancialLossService
from services.monetary_service import MonetaryService


class MonetaryServiceTest(TestCase):
    def test_detects_invoice_total_read_as_toman(self):
        amounts = {
            'order_total': Decimal('130000000'),
            'advance_payment': Decimal('130000000'),
            'payment_request_amount': Decimal('130000000'),
            'invoice_total': Decimal('12700000'),
        }
        normalized = MonetaryService.normalize_amounts(amounts)
        self.assertEqual(normalized['invoice_total'], Decimal('127000000'))

    def test_keeps_consistent_rial_amounts(self):
        amounts = {
            'order_total': Decimal('1000000000'),
            'invoice_total': Decimal('950000000'),
        }
        normalized = MonetaryService.normalize_amounts(amounts)
        self.assertEqual(normalized['order_total'], Decimal('1000000000'))
        self.assertEqual(normalized['invoice_total'], Decimal('950000000'))

    def test_normalizes_import_dict_inplace(self):
        data = {
            'order_total': Decimal('130000000'),
            'invoice_total': Decimal('12700000'),
        }
        MonetaryService.normalize_purchase_data(data)
        self.assertEqual(data['invoice_total'], Decimal('127000000'))


class FinancialLossRialNormalizationTest(TestCase):
    def test_real_case_976_style_invoice_misread_as_toman(self):
        purchase = Purchase.objects.create(
            purchase_number='976',
            product_title='کالا',
            quantity=1,
            unit='عدد',
            order_total=130_000_000,
            advance_payment=130_000_000,
            payment_request_amount=130_000_000,
            invoice_total=12_700_000,
        )
        detail = FinancialLossService.evaluate_purchase(purchase)
        self.assertEqual(detail['invoice_total'], 127_000_000.0)
        self.assertFalse(detail['has_loss'])
        self.assertEqual(detail['difference'], -3_000_000.0)

    def test_loss_after_normalization(self):
        purchase = Purchase.objects.create(
            purchase_number='2001',
            product_title='کالا',
            quantity=1,
            unit='عدد',
            order_total=100_000_000,
            invoice_total=11_000_000,
        )
        detail = FinancialLossService.evaluate_purchase(purchase)
        self.assertEqual(detail['invoice_total'], 110_000_000.0)
        self.assertTrue(detail['has_loss'])
        self.assertEqual(detail['loss_amount'], 10_000_000.0)