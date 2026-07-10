from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0006_purchase_order_deadline_deviated'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchase',
            name='payment_lead_deviated',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='از ثبت واریزی (AP) تا انجام واریزی (AQ) — بر اساس گروه کالایی',
                verbose_name='انحراف لیت‌تایم پرداخت',
            ),
        ),
    ]