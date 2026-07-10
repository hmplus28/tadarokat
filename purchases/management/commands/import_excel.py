import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from services.excel_importer import ExcelImporter


class Command(BaseCommand):
    help = 'Import purchases from Excel file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            nargs='?',
            default=None,
            help='Path to Excel file (default: ./input.xlsx)'
        )
    
    def handle(self, *args, **options):
        file_path = options['file_path']
        
        if not file_path:
            # جستجو در مسیرهای پیش‌فرض
            from services.excel_file_utils import get_input_excel_path, get_panel_excel_path

            candidates = [get_input_excel_path()]
            for cand in candidates:
                if cand.exists():
                    file_path = str(cand)
                    break
        
        if not file_path or not os.path.exists(file_path):
            raise CommandError(f"Excel file not found: {file_path}")
        
        self.stdout.write(f"Importing from: {file_path}")
        
        try:
            stats = ExcelImporter.import_from_excel(
                file_path,
                export_path=str(get_panel_excel_path()),
            )
            
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Import completed successfully:\n"
                f"  - Created: {stats['created']}\n"
                f"  - Updated: {stats['updated']}\n"
                f"  - Skipped: {stats['skipped']}\n"
                f"  - Errors: {len(stats['errors'])}"
            ))
            
            if stats['errors'] and len(stats['errors']) <= 10:
                for err in stats['errors']:
                    self.stdout.write(self.style.WARNING(f"  ⚠️ {err}"))
        
        except Exception as e:
            raise CommandError(f"Import failed: {str(e)}")