from django.db import migrations, models


DEFAULT_CATEGORIES = [
    ('ایمنی و بهداشت', 1),
    ('اقلام مصرفی', 2),
    ('آی تی', 3),
    ('ابنیه و مصالح', 4),
    ('نت و تاسیسات', 5),
    ('عمومی تولید', 6),
    ('چاپ و تبلیغات', 7),
]

CENTRAL_WAREHOUSE_NAMES = ('انبار مرکز', 'انبار مرکزی')


def seed_product_categories(apps, schema_editor):
    ProductCategory = apps.get_model('accounts', 'ProductCategory')
    for name, order in DEFAULT_CATEGORIES:
        ProductCategory.objects.get_or_create(
            name=name,
            defaults={'sort_order': order, 'is_active': True},
        )


def deactivate_central_warehouses(apps, schema_editor):
    Warehouse = apps.get_model('accounts', 'Warehouse')
    Warehouse.objects.filter(name__in=CENTRAL_WAREHOUSE_NAMES).update(is_active=False)


def reverse_seed(apps, schema_editor):
    ProductCategory = apps.get_model('accounts', 'ProductCategory')
    ProductCategory.objects.filter(
        name__in=[name for name, _ in DEFAULT_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_warehouse_user_assigned_warehouse'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='نام گروه')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('sort_order', models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب نمایش')),
            ],
            options={
                'verbose_name': 'گروه کالایی',
                'verbose_name_plural': 'گروه‌های کالایی',
                'db_table': 'product_categories',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.RunPython(seed_product_categories, reverse_seed),
        migrations.RunPython(deactivate_central_warehouses, migrations.RunPython.noop),
    ]