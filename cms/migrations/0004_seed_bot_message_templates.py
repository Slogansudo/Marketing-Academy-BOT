# Bu migratsiya `BotMessageTemplate` jadvalini `cms/bot_texts.py` dagi BOT_TEXTS
# lug'atidan bir martalik "urug'lab" (seed) to'ldiradi. 0003 migratsiya faqat
# bo'sh jadval yaratgan edi — shu qadam bo'lmasa, admin panel konstruktor
# sahifasidagi hech bir kartochka tahrirlanmaydi ("Ma'lumot topilmadi" ko'rinadi),
# chunki bazada birorta ham qator yo'q.
from django.db import migrations

from cms.bot_texts import BOT_TEXTS, BOT_MESSAGE_GROUPS, DEFAULT_LOCKED_SLUGS


def seed_templates(apps, schema_editor):
    BotMessageTemplate = apps.get_model("cms", "BotMessageTemplate")
    existing = set(BotMessageTemplate.objects.values_list("slug", flat=True))

    to_create = []
    for slug, entry in BOT_TEXTS.items():
        if slug in existing:
            continue
        to_create.append(
            BotMessageTemplate(
                slug=slug,
                group=BOT_MESSAGE_GROUPS.get(slug, "main_menu"),
                title=entry["title"],
                text=entry["text"],
                default_text=entry["text"],
                is_locked=slug in DEFAULT_LOCKED_SLUGS,
            )
        )
    if to_create:
        BotMessageTemplate.objects.bulk_create(to_create)


def unseed_templates(apps, schema_editor):
    # Orqaga qaytarilsa — faqat shu migratsiya yaratgan (hali o'zgartirilmagan,
    # default holatidagi) qatorlarni o'chiramiz, admin allaqachon tahrirlagan
    # yozuvlarga tegmaymiz.
    BotMessageTemplate = apps.get_model("cms", "BotMessageTemplate")
    for slug, entry in BOT_TEXTS.items():
        BotMessageTemplate.objects.filter(slug=slug, text=entry["text"], title=entry["title"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0003_botmessagetemplate"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]