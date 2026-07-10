from django.core.management.base import BaseCommand
from django.db import transaction
from purchases.models import Purchase
from deliveries.models import Delivery
from orders.models import Order


class Command(BaseCommand):
    help = 'Sync deliveries from Purchase table (historical data from Excel)'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Finding purchases with delivery information...')
        
        # پیدا کردن تمام خرید‌هایی که شماره تحویل دارند
        purchases_with_delivery = Purchase.objects.exclude(
            delivery_number=''
        ).exclude(
            delivery_number__isnull=True
        )
        
        total = purchases_with_delivery.count()
        self.stdout.write(f'✅ Found {total} purchases with delivery data')
        
        if total == 0:
            self.stdout.write(self.style.WARNING('⚠️  No deliveries to sync'))
            return
        
        created = 0
        updated = 0
        skipped = 0
        errors = []
        
        with transaction.atomic():
            for purchase in purchases_with_delivery:
                try:
                    # بررسی تکراری نبودن
                    if Delivery.objects.filter(delivery_number=purchase.delivery_number).exists():
                        skipped += 1
                        continue
                    
                    # پیدا کردن Order مرتبط (اگر وجود دارد)
                    order = None
                    if purchase.order_number:
                        order = Order.objects.filter(order_number=purchase.order_number).first()
                    
                    # ایجاد رکورد Delivery
                    Delivery.objects.create(
                        delivery_number=purchase.delivery_number,
                        order=order,
                        purchase=purchase,
                        product_title=purchase.product_title or '',
                        quantity=purchase.delivered_quantity or purchase.quantity or 0,
                        unit=purchase.unit or '',
                        warehouse=purchase.supply_unit or '',
                        receiver='',  # در اکسل موجود نیست
                        delivery_date=purchase.delivery_date or '',
                        supplier=purchase.supplier or '',
                        description='',
                    )
                    created += 1
                    
                    if created % 100 == 0:
                        self.stdout.write(f'  Processed {created} deliveries...')
                
                except Exception as e:
                    errors.append(f"Purchase {purchase.purchase_number}: {str(e)}")
                    skipped += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Sync completed:\n'
            f'  - Created: {created}\n'
            f'  - Skipped: {skipped}\n'
            f'  - Errors: {len(errors)}'
        ))
        
        if errors:
            self.stdout.write(self.style.WARNING(f'\n⚠️  First 10 errors:'))
            for err in errors[:10]:
                self.stdout.write(f'  - {err}')