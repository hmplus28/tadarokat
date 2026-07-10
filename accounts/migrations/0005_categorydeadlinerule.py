from django.db import migrations, models
import django.db.models.deletion


DEFAULT_RULES = [
    ('ایمنی و بهداشت', 'month_days', '5,25', 'مهلت ۵ و ۲۵ هر ماه'),
    ('عمومی تولید', 'week_starts', '', 'ابتدای هر هفته ماه'),
    ('اقلام مصرفی', 'month_days', '10,25', 'مهلت ۱۰ و ۲۵ هر ماه (انبار)'),
    ('نت و تاسیسات', 'month_days', '10,25', 'مهلت ۱۰ و ۲۵ هر ماه'),
]


def seed_deadline_rules(apps, schema_editor):
    ProductCategory = apps.get_model('accounts', 'ProductCategory')
    CategoryDeadlineRule = apps.get_model('accounts', 'CategoryDeadlineRule')

    for name, rule_type, allowed_days, notes in DEFAULT_RULES:
        category = ProductCategory.objects.filter(name=name).first()
        if not category:
            continue
        CategoryDeadlineRule.objects.get_or_create(
            category=category,
            defaults={
                'rule_type': rule_type,
                'allowed_days': allowed_days,
                'notes': notes,
                'is_active': True,
            },
        )


def reverse_seed(apps, schema_editor):
    CategoryDeadlineRule = apps.get_model('accounts', 'CategoryDeadlineRule')
    CategoryDeadlineRule.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_productcategory'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoryDeadlineRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rule_type', models.CharField(
                    choices=[('month_days', 'روزهای مشخص ماه'), ('week_starts', 'ابتدای هر هفته ماه')],
                    default='month_days', max_length=20, verbose_name='نوع قانون',
                )),
                ('allowed_days', models.CharField(
                    blank=True, help_text='مثلاً: 5,25 یا 10,25 — فقط برای نوع «روزهای مشخص ماه»',
                    max_length=100, verbose_name='روزهای مجاز ماه',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('notes', models.CharField(blank=True, max_length=200, verbose_name='توضیح')),
                ('category', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deadline_rule', to='accounts.productcategory', verbose_name='گروه کالایی',
                )),
            ],
            options={
                'verbose_name': 'قانون مهلت گروه کالایی',
                'verbose_name_plural': 'قوانین مهلت گروه‌های کالایی',
                'db_table': 'category_deadline_rules',
            },
        ),
        migrations.RunPython(seed_deadline_rules, reverse_seed),
    ]