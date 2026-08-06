import django.utils.timezone
from django.db import migrations, models

from cms.bot_texts import BOT_MESSAGE_CHOICES


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0001_initial'),
    ]

    operations = [
        # Bot matnlari endi bazada emas, kodda (cms.bot_texts) saqlanadi.
        migrations.DeleteModel(
            name='BotText',
        ),
        # BotMedia endi istalgan statik xabar slug'iga biriktirilishi mumkin,
        # shu sababli erkin nomdagi "title" maydoni kerak emas — slug o'zi tanlov ro'yxati.
        migrations.RemoveField(
            model_name='botmedia',
            name='title',
        ),
        migrations.AddField(
            model_name='botmedia',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='botmedia',
            name='slug',
            field=models.SlugField(choices=BOT_MESSAGE_CHOICES, help_text="Qaysi statik bot xabariga biriktirilgan", unique=True),
        ),
    ]
