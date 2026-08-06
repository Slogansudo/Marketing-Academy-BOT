# Avto-to'lov vaqt sozlamalarini (eslatma kunlari, qayta urinish soatlari, max urinish)
# qaytadan, lekin xavfsizroq — BOSQICH-asosidagi (erkin CSV ro'yxat emas) shaklda
# qo'shadi. Qarang: subscriptions/renewal_config.py docstringi.
import django.db.models.deletion
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0005_delete_renewalsettings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RenewalSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reminder_stage_1_days", models.PositiveSmallIntegerField(
                    default=3, validators=[MinValueValidator(1), MaxValueValidator(30)],
                    help_text="1-eslatma ('renewal_reminder_3d' matni) to'lov sanasidan necha kun oldin yuborilsin.",
                )),
                ("reminder_stage_2_days", models.PositiveSmallIntegerField(
                    default=2, validators=[MinValueValidator(1), MaxValueValidator(30)],
                    help_text="2-eslatma ('renewal_reminder_2d' matni) to'lov sanasidan necha kun oldin yuborilsin.",
                )),
                ("reminder_stage_3_days", models.PositiveSmallIntegerField(
                    default=1, validators=[MinValueValidator(1), MaxValueValidator(30)],
                    help_text="3-eslatma ('renewal_reminder_1d' matni) to'lov sanasidan necha kun oldin yuborilsin.",
                )),
                ("sms_on_stage", models.PositiveSmallIntegerField(
                    default=3, validators=[MinValueValidator(0), MaxValueValidator(3)],
                    help_text="Qaysi eslatma bosqichida (1/2/3) SMS ham yuborilsin. 0 = SMS o'chirilgan.",
                )),
                ("retry_wait_hours_stage_1", models.PositiveSmallIntegerField(
                    default=24, validators=[MinValueValidator(1), MaxValueValidator(240)],
                    help_text="1-urinish muvaffaqiyatsiz bo'lsa, 2-urinishgacha necha soat kutilsin.",
                )),
                ("retry_wait_hours_stage_2", models.PositiveSmallIntegerField(
                    default=24, validators=[MinValueValidator(1), MaxValueValidator(240)],
                    help_text="2-urinish muvaffaqiyatsiz bo'lsa, 3-urinishgacha necha soat kutilsin.",
                )),
                ("retry_wait_hours_stage_3", models.PositiveSmallIntegerField(
                    default=18, validators=[MinValueValidator(1), MaxValueValidator(240)],
                    help_text="3-urinish muvaffaqiyatsiz bo'lsa, 4-urinishgacha necha soat kutilsin.",
                )),
                ("retry_wait_hours_stage_4", models.PositiveSmallIntegerField(
                    default=6, validators=[MinValueValidator(1), MaxValueValidator(240)],
                    help_text="4-urinish muvaffaqiyatsiz bo'lsa, 5-urinishgacha (yakuniy) necha soat kutilsin.",
                )),
                ("max_attempts", models.PositiveSmallIntegerField(
                    default=5, validators=[MinValueValidator(2), MaxValueValidator(8)],
                    help_text=(
                        "Jami nechta urinishdan keyin obuna avtomatik bekor qilinsin. 4 tadan ortiq "
                        "qayta urinish uchun alohida matn yo'q — 4-dan keyingi urinishlar '4-urinish' "
                        "matni bilan yuboriladi."
                    ),
                )),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Avto-to'lov vaqt sozlamalari",
                "verbose_name_plural": "Avto-to'lov vaqt sozlamalari",
            },
        ),
    ]