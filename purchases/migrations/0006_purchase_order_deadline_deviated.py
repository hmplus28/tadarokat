from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0005_purchase_deadline_deviated'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchase',
            name='order_deadline_deviated',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='بر اساس مهلت (ستون O) و تاریخ سفارش (ستون AB)',
                verbose_name='انحراف از مهلت سفارش',
            ),
        ),
    ]