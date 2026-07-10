from django.test import TestCase
from purchases.models import Purchase, is_valid_value


class PurchaseModelTest(TestCase):
    def setUp(self):
        self.purchase = Purchase.objects.create(
            purchase_number='1001',
            product_title='تست کالا',
            quantity=10,
            unit='عدد',
            status='در جريان',
            current_status='waiting_inquiry'
        )

    def test_purchase_creation(self):
        """آیا خرید به درستی ایجاد می‌شود؟"""
        self.assertEqual(self.purchase.purchase_number, '1001')
        self.assertEqual(str(self.purchase), '1001 - تست کالا')

    def test_calculate_current_status_delivered(self):
        """محاسبه وضعیت تحویل شده"""
        self.purchase.delivery_date = '1405/04/01'
        self.purchase.save()
        self.assertEqual(self.purchase.current_status, 'delivered')

    def test_calculate_current_status_paid(self):
        """محاسبه وضعیت پرداخت شده"""
        self.purchase.payment_completion_date = '1405/03/20'
        self.purchase.save()
        self.assertEqual(self.purchase.current_status, 'paid')

    def test_calculate_current_status_waiting_payment_with_request_number(self):
        """شماره پرداخت بدون تاریخ انجام واریزی = در انتظار پرداخت"""
        self.purchase.payment_request_number = '627'
        self.purchase.payment_request_amount = 1493400040
        self.purchase.payment_registration_date = '1405/02/08'
        self.purchase.save()
        self.assertEqual(self.purchase.current_status, 'waiting_payment')

    def test_calculate_current_status_registration_date_alone_not_paid(self):
        """تاریخ ثبت واریزی بدون تاریخ انجام واریزی نباید پرداخت‌شده باشد"""
        self.purchase.payment_registration_date = '1405/03/20'
        self.purchase.save()
        self.assertNotEqual(self.purchase.current_status, 'paid')

    def test_calculate_current_status_order_issued(self):
        """محاسبه وضعیت دستور صادر شده"""
        self.purchase.order_number = '7001'
        self.purchase.save()
        self.assertEqual(self.purchase.current_status, 'order_issued')

    def test_can_issue_inquiry_true(self):
        """امکان صدور استعلام برای خرید اولیه"""
        self.assertTrue(self.purchase.can_issue_inquiry)

    def test_can_issue_inquiry_false_when_ordered(self):
        """عدم امکان صدور استعلام پس از صدور دستور"""
        self.purchase.order_number = '7001'
        self.purchase.save()
        self.assertFalse(self.purchase.can_issue_inquiry)

    def test_can_issue_inquiry_false_when_inquiry_issued(self):
        """عدم امکان صدور استعلام پس از ثبت شماره استعلام"""
        self.purchase.inquiry_number = '8842'
        self.purchase.save()
        self.assertFalse(self.purchase.can_issue_inquiry)

    def test_has_placeholder_workflow_fields(self):
        """تشخیص متن placeholder اکسل"""
        self.purchase.payment_request_number = 'در انتظار تکمیل روند خرید'
        self.purchase.save()
        self.assertTrue(self.purchase.has_placeholder_workflow_fields)

    def test_payment_placeholder_not_valid_workflow_value(self):
        """متن placeholder اکسل نباید مرحله پرداخت را تکمیل‌شده نشان دهد"""
        self.purchase.payment_request_number = 'در انتظار تکمیل روند خرید'
        self.purchase.save()
        self.assertFalse(is_valid_value(self.purchase.payment_request_number))

    def test_can_issue_order_true_with_inquiry(self):
        """مدیر می‌تواند پس از استعلام دستور صادر کند"""
        self.purchase.inquiry_number = '8842'
        self.purchase.save()
        self.assertTrue(self.purchase.can_issue_order)

    def test_can_issue_order_false_when_order_exists(self):
        """اگر دستور قبلاً صادر شده، امکان صدور مجدد نیست"""
        self.purchase.inquiry_number = '8842'
        self.purchase.order_number = '7303'
        self.purchase.save()
        self.assertFalse(self.purchase.can_issue_order)

    def test_order_stopped_status_when_order_request_stopped(self):
        """سفارش متوقف‌شده نباید «سفارش صادر شده» نشان دهد"""
        self.purchase.order_request_number = '19902'
        self.purchase.order_request_status = 'متوقف شده'
        self.purchase.status = 'بسته شده'
        self.purchase.save()
        self.assertEqual(self.purchase.current_status, 'order_stopped')
        self.assertTrue(self.purchase.is_order_stopped)
        self.assertEqual(self.purchase.display_status, 'متوقف شده')