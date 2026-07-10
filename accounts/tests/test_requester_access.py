from django.test import TestCase

from accounts.models import User
from accounts.requester_access import (
    filter_purchases_for_requester,
    requester_can_view_purchase,
)
from inquiries.models import Inquiry
from orders.models import Order
from purchases.models import Purchase


class RequesterAccessTest(TestCase):
    def setUp(self):
        self.it_user = User.objects.create_user(
            username='it_user',
            email='it@test.local',
            password='pass',
            role='requester',
            requester_scope='it',
        )
        self.abnieh_user = User.objects.create_user(
            username='abnieh_user',
            email='abnieh@test.local',
            password='pass',
            role='requester',
            requester_scope='abnieh',
        )

    def test_filter_by_product_category(self):
        it_purchase = Purchase.objects.create(
            purchase_number='5001',
            product_title='لپ‌تاپ',
            quantity=1,
            unit='عدد',
            product_category='آی تی',
        )
        other = Purchase.objects.create(
            purchase_number='5002',
            product_title='سیمان',
            quantity=1,
            unit='عدد',
            product_category='ابنیه و مصالح',
        )
        qs = filter_purchases_for_requester(Purchase.objects.all(), self.it_user)
        self.assertEqual(list(qs.values_list('pk', flat=True)), [it_purchase.pk])
        self.assertFalse(requester_can_view_purchase(other, self.it_user))

    def test_filter_by_inquiry_warehouse(self):
        purchase = Purchase.objects.create(
            purchase_number='5003',
            product_title='کالا ابنیه',
            quantity=1,
            unit='عدد',
            inquiry_number='9001',
        )
        Inquiry.objects.create(
            inquiry_number='9001',
            purchase=purchase,
            inquiry_date='1405/04/01',
            warehouse='انبار ابنیه',
        )
        qs = filter_purchases_for_requester(Purchase.objects.all(), self.abnieh_user)
        self.assertTrue(qs.filter(pk=purchase.pk).exists())

    def test_filter_by_order_warehouse(self):
        purchase = Purchase.objects.create(
            purchase_number='5004',
            product_title='کالا نت',
            quantity=1,
            unit='عدد',
        )
        Order.objects.create(
            order_number='8001',
            purchase=purchase,
            product_title='کالا نت',
            quantity=1,
            order_date='1405/04/01',
            warehouse='انبار نت',
        )
        tolid_user = User.objects.create_user(
            username='tolid_user',
            email='tolid@test.local',
            password='pass',
            role='requester',
            requester_scope='tolid',
        )
        qs = filter_purchases_for_requester(Purchase.objects.all(), tolid_user)
        self.assertTrue(qs.filter(pk=purchase.pk).exists())