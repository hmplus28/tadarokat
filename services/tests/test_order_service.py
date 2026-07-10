from django.test import TestCase
from django.contrib.auth import get_user_model
from purchases.models import Purchase
from orders.models import Order
from services.order_service import OrderService, STAGE_FLOW

User = get_user_model()


class OrderServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com',  # ← ایمیل اضافه شد
            password='pass', 
            role='expert'
        )
        self.purchase = Purchase.objects.create(
            purchase_number='2001', product_title='کالا تست', 
            quantity=5, unit='عدد', preinvoice_price=1000
        )
        self.order = OrderService.create_from_purchase(
            self.purchase, self.user, {'contractor': 'تامین کننده تست'}
        )

    def test_create_order_from_purchase(self):
        """ایجاد دستور از خرید"""
        self.assertIsNotNone(self.order.pk)
        self.assertEqual(self.order.stage, 'order_issued')
        self.assertEqual(self.order.total_price, 5000)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.order_number, self.order.order_number)
        self.assertEqual(self.purchase.current_status, 'order_issued')

    def test_advance_stage_to_order_placed(self):
        """پیشبرد مرحله از order_issued به order_placed"""
        # وقتی در مرحله order_issued هستیم و فیلدهای payment را پر می‌کنیم،
        # سیستم مرحله را به order_placed تغییر می‌دهد
        updated = OrderService.advance_stage(self.order, {
            'payment_number': 'PAY-001',
            'payment_date': '1405/04/05'
        }, 'testuser')
        
        # مرحله باید order_placed باشد (نه payment)
        self.assertEqual(updated.stage, 'order_placed')
        # اما فیلدهای پرداخت باید ذخیره شده باشند
        self.assertEqual(updated.payment_number, 'PAY-001')
        self.assertEqual(updated.payment_date, '1405/04/05')

    def test_advance_stage_missing_required_fields(self):
        """خطا هنگام فقدان فیلدهای الزامی"""
        with self.assertRaises(ValueError) as ctx:
            OrderService.advance_stage(self.order, {
                'payment_number': '',
                'payment_date': ''
            }, 'testuser')
        self.assertIn('الزامی', str(ctx.exception))

    def test_cannot_advance_completed_order(self):
        """عدم امکان پیشبرد دستور تکمیل شده"""
        self.order.stage = 'delivered'
        self.order.save()
        
        with self.assertRaises(ValueError):
            OrderService.advance_stage(self.order, {}, 'testuser')