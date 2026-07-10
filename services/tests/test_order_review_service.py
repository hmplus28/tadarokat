from django.contrib.auth import get_user_model
from django.test import TestCase

from inquiries.models import Inquiry
from purchases.models import Purchase
from services.order_review_service import OrderReviewService

User = get_user_model()


class OrderReviewServiceTest(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='mgr', email='mgr@test.local', password='pass', role='admin',
        )
        self.expert_a = User.objects.create_user(
            username='exp_a', email='a@test.local', password='pass',
            role='expert', expert_name='کارشناس الف',
        )
        self.expert_b = User.objects.create_user(
            username='exp_b', email='b@test.local', password='pass',
            role='expert', expert_name='کارشناس ب',
        )
        self.purchase = Purchase.objects.create(
            purchase_number='2001',
            line_number=1,
            product_title='کالای تست',
            quantity=2,
            unit='عدد',
            expert_name='کارشناس الف',
            inquiry_number='9100',
            status='در جريان',
        )
        self.inquiry = Inquiry.objects.create(
            inquiry_number='9100',
            purchase=self.purchase,
            inquiry_date='1405/04/01',
            expert_name='کارشناس الف',
            status=Inquiry.Status.ISSUED,
            created_by=self.expert_a,
        )

    def test_pending_queue_includes_ready_purchase(self):
        items = OrderReviewService.get_pending_queue()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].pk, self.purchase.pk)

    def test_reassign_expert_updates_purchase_and_inquiry(self):
        result = OrderReviewService.reassign_expert(
            [self.purchase.pk], 'کارشناس ب', self.manager, note='ارجاع تست',
        )
        self.assertEqual(result['updated'], 1)
        self.purchase.refresh_from_db()
        self.inquiry.refresh_from_db()
        self.assertEqual(self.purchase.expert_name, 'کارشناس ب')
        self.assertEqual(self.inquiry.expert_name, 'کارشناس ب')
        self.assertTrue(self.purchase.can_issue_order)

    def test_return_for_reinquiry_clears_inquiry_and_allows_new_inquiry(self):
        result = OrderReviewService.return_for_reinquiry(
            [self.purchase.pk],
            self.manager,
            note='قیمت‌ها نامناسب',
            new_expert_name='کارشناس ب',
        )
        self.assertEqual(result['returned'], 1)
        self.purchase.refresh_from_db()
        self.inquiry.refresh_from_db()
        self.assertEqual(self.purchase.inquiry_number, '')
        self.assertEqual(self.purchase.current_status, 'waiting_inquiry')
        self.assertTrue(self.purchase.can_issue_inquiry)
        self.assertFalse(self.purchase.can_issue_order)
        self.assertEqual(self.inquiry.status, Inquiry.Status.REJECTED)
        self.assertEqual(self.purchase.expert_name, 'کارشناس ب')

    def test_return_requires_note(self):
        with self.assertRaises(ValueError):
            OrderReviewService.return_for_reinquiry(
                [self.purchase.pk], self.manager, note='',
            )