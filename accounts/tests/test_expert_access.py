from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.expert_access import (
    filter_purchases_for_expert,
    expert_can_view_purchase,
    is_pure_expert_user,
)
from purchases.models import Purchase

User = get_user_model()


class ExpertAccessTest(TestCase):
    def setUp(self):
        self.expert = User.objects.create_user(
            username='exp1', email='e1@test.local', password='pass',
            role='expert', expert_name='کارشناس الف',
        )
        self.other_expert = User.objects.create_user(
            username='exp2', email='e2@test.local', password='pass',
            role='expert', expert_name='کارشناس ب',
        )
        self.admin = User.objects.create_user(
            username='admin1', email='a@test.local', password='pass', role='admin',
        )
        self.mine = Purchase.objects.create(
            purchase_number='3001', line_number=1, product_title='کالای من',
            expert_name='کارشناس الف', status='در جريان',
        )
        self.theirs = Purchase.objects.create(
            purchase_number='3002', line_number=1, product_title='کالای دیگر',
            expert_name='کارشناس ب', status='در جريان',
        )

    def test_pure_expert_detection(self):
        self.assertTrue(is_pure_expert_user(self.expert))
        self.assertFalse(is_pure_expert_user(self.admin))

    def test_expert_sees_only_own_purchases(self):
        qs = filter_purchases_for_expert(Purchase.objects.all(), self.expert)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.mine.pk)

    def test_expert_cannot_view_others_purchase(self):
        self.assertTrue(expert_can_view_purchase(self.mine, self.expert))
        self.assertFalse(expert_can_view_purchase(self.theirs, self.expert))

    def test_admin_sees_all(self):
        qs = filter_purchases_for_expert(Purchase.objects.all(), self.admin)
        self.assertEqual(qs.count(), 2)