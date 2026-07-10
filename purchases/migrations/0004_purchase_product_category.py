from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0003_alter_purchase_payment_registration_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchase',
            name='product_category',
            field=models.CharField(blank=True, db_index=True, max_length=100, verbose_name='گروه بندی کالایی'),
        ),
    ]