# BotMedia endi istalgan turdagi media (video/audio/rasm) saqlaydi, video uchun
# qo'shimcha shakl (to'rtburchak/dumaloq) tanlanadi. Eski `video` FileField `file`ga
# nomi o'zgartiriladi (mavjud fayllar shu bilan saqlanib qoladi, faqat maydon nomi
# o'zgaradi — fizik fayl yo'li o'zgarmaydi).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0005_alter_botmessagetemplate_options_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="botmedia",
            old_name="video",
            new_name="file",
        ),
        migrations.AlterField(
            model_name="botmedia",
            name="file",
            field=models.FileField(blank=True, help_text="Yuklangan media fayl (video/audio/rasm)", null=True, upload_to="bot_media/"),
        ),
        migrations.AlterField(
            model_name="botmedia",
            name="video_url",
            field=models.URLField(
                blank=True, null=True,
                help_text="Fayl o'rniga tashqi video URL/Telegram file_id (faqat media_type=video, dumaloq shakl uchun ishlamaydi)",
            ),
        ),
        migrations.AddField(
            model_name="botmedia",
            name="media_type",
            field=models.CharField(
                choices=[("video", "Video"), ("audio", "Audio"), ("photo", "Rasm")],
                default="video",
                help_text="Qanday turdagi media — botda shu turga mos Telegram metodi bilan yuboriladi",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="botmedia",
            name="video_shape",
            field=models.CharField(
                blank=True,
                choices=[("rectangle", "To'rtburchak (oddiy video)"), ("circle", "Dumaloq (video xabar)")],
                default="rectangle",
                help_text=(
                    "Faqat media_type=video bo'lsa ma'noli. 'Dumaloq' — Telegramning video-xabar "
                    "(video note) formati; bu faqat yuklangan faylga ishlaydi, tashqi URL'ga emas, "
                    "va caption (matn) qo'llab-quvvatlanmaydi — matn video ostida alohida xabar sifatida ketadi."
                ),
                max_length=10,
            ),
        ),
    ]
