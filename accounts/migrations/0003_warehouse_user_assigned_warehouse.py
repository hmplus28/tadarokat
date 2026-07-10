from django.db import migrations, models
import django.db.models.deletion


DEFAULT_WAREHOUSES = [
    ('انبار مصرفی', 1),
    ('انبار نت', 2),
    ('انبار تاسیسات', 3),
]


def seed_warehouses_and_migrate_users(apps, schema_editor):
    Warehouse = apps.get_model('accounts', 'Warehouse')
    User = apps.get_model('accounts', 'User')

    warehouse_by_name = {}
    for name, order in DEFAULT_WAREHOUSES:
        wh, _ = Warehouse.objects.get_or_create(
            name=name,
            defaults={'sort_order': order, 'is_active': True},
        )
        warehouse_by_name[name] = wh

    for user in User.objects.all():
        old_name = getattr(user, 'warehouse', '') or ''
        if not old_name:
            continue
        wh = warehouse_by_name.get(old_name)
        if not wh:
            wh, _ = Warehouse.objects.get_or_create(
                name=old_name,
                defaults={'sort_order': 100, 'is_active': True},
            )
            warehouse_by_name[old_name] = wh
        user.assigned_warehouse = wh
        user.save(update_fields=['assigned_warehouse'])


def reverse_migration(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.select_related('assigned_warehouse').all():
        if user.assigned_warehouse_id:
            user.warehouse = user.assigned_warehouse.name
            user.save(update_fields=['warehouse'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_national_id_alter_user_expert_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Warehouse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='نام انبار')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('sort_order', models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب نمایش')),
            ],
            options={
                'verbose_name': 'انبار',
                'verbose_name_plural': 'انبارها',
                'db_table': 'warehouses',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.AddField(
            model_name='user',
            name='assigned_warehouse',
            field=models.ForeignKey(
                blank=True,
                help_text='فقط برای نقش انباردار',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users',
                to='accounts.warehouse',
                verbose_name='انبار مسئول',
            ),
        ),
        migrations.RunPython(seed_warehouses_and_migrate_users, reverse_migration),
        migrations.RemoveField(
            model_name='user',
            name='warehouse',
        ),
    ]