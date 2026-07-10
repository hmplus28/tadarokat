from django.core.management.base import BaseCommand
from purchases.models import Purchase


class Command(BaseCommand):
    help = 'Recalculate current_status for all purchases'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Recalculating current_status for all purchases...')
        
        total = Purchase.objects.count()
        updated = 0
        
        for purchase in Purchase.objects.all():
            old_status = purchase.current_status
            new_status = purchase.calculate_current_status()
            
            if old_status != new_status:
                purchase.current_status = new_status
                purchase.save(update_fields=['current_status'])
                updated += 1
                
                if updated % 100 == 0:
                    self.stdout.write(f'  Processed {updated} updates...')
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Recalculation completed:\n'
            f'  - Total purchases: {total}\n'
            f'  - Updated: {updated}\n'
            f'  - Unchanged: {total - updated}'
        ))