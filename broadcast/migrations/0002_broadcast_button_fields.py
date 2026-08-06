from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('broadcast', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='broadcast',
            name='button_text',
            field=models.CharField(
                blank=True, null=True, max_length=64,
                help_text="Ixtiyoriy inline tugma matni (masalan: 'Batafsil'). Bo'sh bo'lsa tugma chiqmaydi.",
            ),
        ),
        migrations.AddField(
            model_name='broadcast',
            name='button_url',
            field=models.URLField(
                blank=True, null=True,
                help_text="Ixtiyoriy inline tugma bosilganda ochiladigan havola",
            ),
        ),
    ]
