# Konstruktor canvasida kartochkalarni sudrab guruh ichida tartibini
# o'zgartirish uchun `position` maydoni. Botning haqiqiy yuborish tartibiga
# bu ta'sir qilmaydi (u hamon kod ichida belgilangan) — bu faqat admin
# panelidagi vizual tartib. Boshlang'ich qiymatlar hozirgi (kod ichidagi)
# ko'rinishni saqlab qolish uchun `BOT_MESSAGE_GROUPS` lug'atining
# yozilish tartibidan olinadi.
from django.db import migrations, models

from cms.bot_texts import BOT_MESSAGE_GROUPS


def seed_positions(apps, schema_editor):
    BotMessageTemplate = apps.get_model("cms", "BotMessageTemplate")
    counters = {}
    order_by_slug = {slug: i for i, slug in enumerate(BOT_MESSAGE_GROUPS)}
    for template in BotMessageTemplate.objects.all():
        group = template.group
        idx = order_by_slug.get(template.slug)
        if idx is not None:
            position = idx
        else:
            position = counters.get(group, 0)
        counters[group] = counters.get(group, 0) + 1
        template.position = position
        template.save(update_fields=["position"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0004_seed_bot_message_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="botmessagetemplate",
            name="position",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Admin konstruktoridagi kartochka tartibi (guruh ichida). Faqat "
                    "ko'rinish/tashkillashtirish uchun — botning haqiqiy yuborish tartibiga "
                    "ta'sir qilmaydi (u kod bilan belgilangan)."
                ),
            ),
        ),
        migrations.AlterModelOptions(
            name="botmessagetemplate",
            options={
                "ordering": ["group", "position", "slug"],
                "verbose_name": "Bot xabari (tahrirlanadigan)",
                "verbose_name_plural": "Bot xabarlari (tahrirlanadigan)",
            },
        ),
        migrations.RunPython(seed_positions, noop),
    ]
