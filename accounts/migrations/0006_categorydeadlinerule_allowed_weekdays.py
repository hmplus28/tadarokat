from django.db import migrations, models


def migrate_week_starts_to_weekdays(apps, schema_editor):
    CategoryDeadlineRule = apps.get_model('accounts', 'CategoryDeadlineRule')
    for rule in CategoryDeadlineRule.objects.filter(rule_type='week_starts'):
        if not rule.allowed_weekdays:
            rule.allowed_weekdays = '0'
            rule.save(update_fields=['allowed_weekdays'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_categorydeadlinerule'),
    ]

    operations = [
        migrations.AddField(
            model_name='categorydeadlinerule',
            name='allowed_weekdays',
            field=models.CharField(
                blank=True,
                help_text='روزهای هفته شمسی: 0=شنبه، 1=یکشنبه، ... 6=جمعه — با کاما جدا شود',
                max_length=30,
                verbose_name='روزهای هفته مجاز',
            ),
        ),
        migrations.RunPython(migrate_week_starts_to_weekdays, migrations.RunPython.noop),
    ]