import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from services.excel_importer import ExcelImporter


class Command(BaseCommand):
    help = 'Sync purchases from Excel (smart mode - preserves workflow data)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            nargs='?',
            default=None,
            help='Path to Excel file'
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Full sync mode (DANGEROUS - overwrites workflow fields)',
        )
    
    def handle(self, *args, **options):
        file_path = options['file_path']
        full_sync = options['full']
        
        if not file_path:
            from services.excel_file_utils import get_input_excel_path, get_panel_excel_path

            candidates = [get_input_excel_path()]
            for cand in candidates:
                if cand.exists():
                    file_path = str(cand)
                    break
        
        if not file_path or not os.path.exists(file_path):
            raise CommandError(f"Excel file not found: {file_path}")
        
        self.stdout.write(f"📥 Syncing from: {file_path}")
        self.stdout.write(f"🔧 Mode: {'FULL (dangerous)' if full_sync else 'SMART (safe)'}")
        
        try:
            stats = ExcelImporter.import_from_excel(
                file_path,
                full_sync=full_sync,
                export_path=str(get_panel_excel_path()),
            )
            
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Sync completed successfully:\n"
                f"  - Created: {stats['created']}\n"
                f"  - Updated: {stats['updated']}\n"
                f"  - Workflow preserved: {stats['workflow_preserved']}\n"
                f"  - Skipped: {stats['skipped']}\n"
                f"  - Errors: {len(stats['errors'])}"
            ))
        
        except Exception as e:
            raise CommandError(f"Sync failed: {str(e)}")