from decimal import Decimal

from django.test import TestCase

from purchases.models import Purchase
from services.financial_loss_service import FinancialLossService


class FinancialLossServiceTest(TestCase):
    def test_loss_when_invoice_exceeds_order_total(self):
        purchase = Purchase.objects.create(
            purchase_number='1001',
            product_title='کالا',
            quantity=1,
            unit='عدد',
            order_total=1_000_000,
            advance_payment=200_000,
            payment_request_amount=800_000,
            invoice_total=1_200_000,
        )
        detail = FinancialLossService.evaluate_purchase(purchase)
        self.assertTrue(detail['has_loss'])
        self.assertEqual(detail['loss_amount'], 200_000.0)
        self.assertEqual(detail['loss_rate'], 20.0)

    def test_no_loss_when_invoice_below_order_total(self):
        purchase = Purchase.objects.create(
            purchase_number='1002',
            product_title='کالا',
            quantity=1,
            unit='عدد',
            order_total=1_000_000,
            invoice_total=900_000,
        )
        detail = FinancialLossService.evaluate_purchase(purchase)
        self.assertFalse(detail['has_loss'])

    def test_budget_is_not_sum_of_ac_ad_an(self):
        purchase = Purchase.objects.create(
            purchase_number='1003',
            product_title='کالا',
            quantity=1,
            unit='عدد',
            order_total=500_000,
            advance_payment=300_000,
            payment_request_amount=400_000,
            invoice_total=600_000,
        )
        detail = FinancialLossService.evaluate_purchase(purchase)
        self.assertEqual(detail['loss_amount'], 100_000.0)
        self.assertNotEqual(
            detail['loss_amount'],
            float(Decimal('600000') - (Decimal('500000') + Decimal('300000') + Decimal('400000'))),
        )

    def test_build_report_single_pass(self):
        Purchase.objects.create(
            purchase_number='2001',
            product_title='کالای ۱',
            quantity=1,
            unit='عدد',
            expert_name='کارشناس الف',
            product_category='آی تی',
            order_total=1_000_000,
            invoice_total=1_100_000,
        )
        Purchase.objects.create(
            purchase_number='2002',
            product_title='کالای ۲',
            quantity=1,
            unit='عدد',
            expert_name='کارشناس ب',
            product_category='ابنیه و مصالح',
            order_total=2_000_000,
            invoice_total=1_800_000,
        )
        Purchase.objects.create(
            purchase_number='2003',
            product_title='ناقص',
            quantity=1,
            unit='عدد',
            order_total=0,
            invoice_total=0,
        )

        report = FinancialLossService.build_report(Purchase.objects.all())
        self.assertEqual(report['overall']['evaluated'], 2)
        self.assertEqual(report['overall']['with_loss'], 1)
        self.assertEqual(report['loss_total'], 1)
        self.assertEqual(report['loss_cases'][0]['purchase_number'], '2001')

    def test_duplicate_purchase_and_order_shown_once(self):
        for i in range(3):
            Purchase.objects.create(
                purchase_number='338',
                line_number=i + 1,
                product_title=f'قلم {i}',
                product_code=f'C{i}',
                quantity=1,
                unit='عدد',
                order_request_number='19809',
                order_total=1_102_398_000,
                invoice_total=1_200_000_000,
            )

        report = FinancialLossService.build_report(Purchase.objects.all())
        self.assertEqual(report['overall']['evaluated'], 1)
        self.assertEqual(report['overall']['with_loss'], 1)
        self.assertEqual(report['loss_total'], 1)
        self.assertEqual(report['loss_cases'][0]['order_request_number'], '19809')