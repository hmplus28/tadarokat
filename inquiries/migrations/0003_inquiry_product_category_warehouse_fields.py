from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inquiries', '0002_preinvoice_preinvoiceline'),
    ]

    operations = [
        migrations.AddField(
            model_name='inquiry',
            name='product_category',
            field=models.CharField(blank=True, max_length=100, verbose_name='گروه بندی کالایی'),
        ),
        migrations.AddField(
            model_name='inquiry',
            name='warehouse_request_number',
            field=models.CharField(blank=True, max_length=50, verbose_name='شماره درخواست کالا از انبار'),
        ),
        migrations.AddField(
            model_name='inquiry',
            name='warehouse_request_date',
            field=models.CharField(blank=True, max_length=20, verbose_name='تاریخ ثبت کالا از انبار'),
        ),
    ]