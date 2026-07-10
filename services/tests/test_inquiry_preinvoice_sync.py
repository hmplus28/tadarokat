from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from inquiries.models import Inquiry, PreInvoice, PreInvoiceLine
from purchases.models import Purchase
from services.inquiry_service import InquiryService

User = get_user_model()


class InquiryPreinvoiceSyncTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='exp', email='e@test.local', password='pass', role='expert',
        )
        self.purchase = Purchase.objects.create(
            purchase_number='4001',
            line_number=1,
            product_title='کالای تست',
            quantity=10,
            unit='عدد',
            status='در جريان',
        )
        self.inquiry = Inquiry.objects.create(
            inquiry_number='9200',
            purchase=self.purchase,
            inquiry_date='1405/05/01',
            created_by=self.user,
        )

    def _make_preinvoice(self, contractor, unit_price, discount=0, selected=False):
        pi = PreInvoice.objects.create(
            inquiry=self.inquiry,
            contractor=contractor,
            invoice_number='PI-001',
            discount=discount,
            is_selected=selected,
        )
        PreInvoiceLine.objects.create(
            pre_invoice=pi,
            product_title='کالای تست',
            quantity=10,
            unit='عدد',
            unit_price=unit_price,
        )
        return pi

    def test_discount_syncs_to_purchase_deductions(self):
        self._make_preinvoice('پیمانکار الف', 100_000, discount=500_000, selected=True)
        InquiryService.sync_purchase_from_inquiry(self.purchase, self.inquiry)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.deductions, Decimal('500000'))
        self.assertEqual(self.purchase.preinvoice_price, Decimal('100000'))
        self.assertEqual(self.purchase.preinvoice_total, Decimal('1000000'))
        self.assertEqual(self.purchase.supplier, 'پیمانکار الف')

    def test_picks_lowest_total_when_none_selected(self):
        self._make_preinvoice('گران', 200_000, discount=0)
        self._make_preinvoice('ارزان', 80_000, discount=100_000)
        InquiryService.sync_purchase_from_inquiry(self.purchase, self.inquiry)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.supplier, 'ارزان')
        self.assertEqual(self.purchase.deductions, Decimal('100000'))