from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0004_purchase_product_category'),
        ('accounts', '0005_categorydeadlinerule'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchase',
            name='deadline_deviated',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='بر اساس تاریخ درخواست (ستون D) و قانون گروه کالایی',
                verbose_name='انحراف از مهلت',
            ),
        ),
    ]