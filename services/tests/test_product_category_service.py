from django.test import TestCase

from accounts.models import ProductCategory
from purchases.models import Purchase
from services.product_category_service import ProductCategoryService


class ProductCategoryServiceTest(TestCase):
    def test_ensure_categories_creates_only_new(self):
        ProductCategory.objects.get_or_create(name='آی تی', defaults={'sort_order': 1})
        created = ProductCategoryService.ensure_categories(['آی تی', 'گروه جدید'])
        self.assertEqual(created, 1)
        self.assertTrue(ProductCategory.objects.filter(name='گروه جدید').exists())

    def test_sync_from_purchases(self):
        Purchase.objects.create(
            purchase_number='5001',
            line_number=1,
            product_title='کالا',
            quantity=1,
            unit='عدد',
            product_category='ابنیه تست',
        )
        created = ProductCategoryService.sync_from_purchases()
        self.assertEqual(created, 1)
        self.assertTrue(ProductCategory.objects.filter(name='ابنیه تست').exists())