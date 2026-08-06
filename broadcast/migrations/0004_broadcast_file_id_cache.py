# Broadcast (e'lon) yuborishda katta media fayllar HAR BIR foydalanuvchi uchun qayta
# yuklanmasligi uchun: birinchi muvaffaqiyatli yuborishdan keyin Telegram qaytargan
# file_id shu yerda keshlanadi, keyingi barcha qabul qiluvchilarga o'sha file_id
# orqali (fayl diskdan o'qilmasdan) tezkor yuboriladi.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('broadcast', '0003_broadcast_is_video_note_broadcast_scheduled_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='broadcast',
            name='image_file_id',
            field=models.CharField(
                blank=True, null=True, max_length=255,
                help_text="Qayta yuklamaslik uchun keshlangan Telegram file_id (rasm birinchi marta yuborilgandan keyin avtomatik saqlanadi)",
            ),
        ),
        migrations.AddField(
            model_name='broadcast',
            name='video_file_id',
            field=models.CharField(
                blank=True, null=True, max_length=255,
                help_text="Qayta yuklamaslik uchun keshlangan Telegram file_id (video birinchi marta yuborilgandan keyin avtomatik saqlanadi)",
            ),
        ),
    ]