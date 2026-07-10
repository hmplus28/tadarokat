"""ساخت کاربر ادمین پیش‌فرض در اولین اجرا (فقط اگر ادمینی نباشد)."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin1234'
DEFAULT_EMAIL = 'admin@local'


class Command(BaseCommand):
    help = 'ایجاد ادمین پیش‌فرض در صورت نبود کاربر سوپر'

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.SUCCESS('ادمین از قبل وجود دارد — رد شد.'))
            return

        User.objects.create_superuser(
            username=DEFAULT_USERNAME,
            email=DEFAULT_EMAIL,
            password=DEFAULT_PASSWORD,
        )
        self.stdout.write(self.style.SUCCESS(
            f'کاربر ادمین ساخته شد — نام کاربری: {DEFAULT_USERNAME} / رمز: {DEFAULT_PASSWORD}'
        ))