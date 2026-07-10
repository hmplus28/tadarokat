from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_categorydeadlinerule_allowed_weekdays'),
    ]

    operations = [
        migrations.AddField(
            model_name='productcategory',
            name='code_prefixes',
            field=models.CharField(
                blank=True,
                help_text='پیشوند کد قلم خریدنی — با کاما جدا شود. برای تخصیص خودکار گروه به پرونده‌های قدیمی',
                max_length=255,
                verbose_name='پیشوند کد کالا',
            ),
        ),
    ]