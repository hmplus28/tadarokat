from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_productcategory_code_prefixes'),
    ]

    operations = [
        migrations.AddField(
            model_name='productcategory',
            name='payment_lead_days',
            field=models.PositiveSmallIntegerField(
                default=7,
                help_text='حداکثر روز مجاز از ثبت واریزی (AP) تا انجام واریزی (AQ)',
                verbose_name='لیت‌تایم پرداخت (روز)',
            ),
        ),
    ]