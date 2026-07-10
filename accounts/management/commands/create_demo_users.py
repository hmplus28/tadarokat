from django.core.management.base import BaseCommand
from accounts.models import User, Warehouse


DEMO_USERS = [
    {
        'username': 'super_demo',
        'email': 'super_demo@tadarokat.local',
        'role': 'superuser',
        'first_name': 'سوپر',
        'last_name': 'یوزر',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'admin_demo',
        'email': 'admin_demo@tadarokat.local',
        'role': 'admin',
        'first_name': 'مدیر',
        'last_name': 'تدارکات',
        'is_staff': True,
    },
    {
        'username': 'expert_demo',
        'email': 'expert_demo@tadarokat.local',
        'role': 'expert',
        'first_name': 'کارشناس',
        'last_name': 'نمونه',
        'expert_name': 'کارشناس نمونه',
    },
    {
        'username': 'warehouse_demo',
        'email': 'warehouse_demo@tadarokat.local',
        'role': 'warehouse',
        'first_name': 'انباردار',
        'last_name': 'نمونه',
        'warehouse_name': 'انبار مصرفی',
    },
    {
        'username': 'it_requester',
        'email': 'it_requester@tadarokat.local',
        'role': 'requester',
        'requester_scope': 'it',
        'first_name': 'واحد',
        'last_name': 'آی‌تی',
    },
    {
        'username': 'abnieh_requester',
        'email': 'abnieh_requester@tadarokat.local',
        'role': 'requester',
        'requester_scope': 'abnieh',
        'first_name': 'واحد',
        'last_name': 'ابنیه',
    },
    {
        'username': 'tolid_requester',
        'email': 'tolid_requester@tadarokat.local',
        'role': 'requester',
        'requester_scope': 'tolid',
        'first_name': 'واحد',
        'last_name': 'تولید',
    },
]


class Command(BaseCommand):
    help = 'ایجاد کاربر نمونه برای هر نقش (رمز: 123)'

    def handle(self, *args, **options):
        password = '123'
        default_warehouses = ['انبار مصرفی', 'انبار نت', 'انبار تاسیسات']
        for i, name in enumerate(default_warehouses, start=1):
            Warehouse.objects.get_or_create(name=name, defaults={'sort_order': i})

        for spec in DEMO_USERS:
            username = spec['username']
            defaults = {k: v for k, v in spec.items() if k not in ('username', 'warehouse_name')}
            wh_name = spec.get('warehouse_name')
            if wh_name:
                defaults['assigned_warehouse'] = Warehouse.objects.get(name=wh_name)
            user, created = User.objects.update_or_create(
                username=username,
                defaults=defaults,
            )
            user.set_password(password)
            user.is_active = True
            user.save()
            action = 'ساخته شد' if created else 'به‌روز شد'
            self.stdout.write(self.style.SUCCESS(
                f'{username} ({spec["role"]}) — {action} | رمز: {password}'
            ))