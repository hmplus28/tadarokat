from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_productcategory_payment_lead_days'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='requester_scope',
            field=models.CharField(
                blank=True,
                choices=[
                    ('it', 'آی‌تی'),
                    ('abnieh', 'ابنیه و عمران'),
                    ('tolid', 'تولید و نت'),
                ],
                default='',
                help_text='فقط برای نقش درخواست‌دهنده — تعیین واحد/گروه قابل مشاهده',
                max_length=20,
                verbose_name='حوزه درخواست‌دهنده',
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('superuser', 'سوپر یوزر'),
                    ('admin', 'مدیر تدارکات'),
                    ('expert', 'کارشناس تدارکات'),
                    ('warehouse', 'انباردار'),
                    ('requester', 'درخواست‌دهنده'),
                ],
                db_index=True,
                default='expert',
                max_length=20,
                verbose_name='نقش',
            ),
        ),
    ]