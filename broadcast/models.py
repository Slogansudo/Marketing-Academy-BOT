from django.db import models
from django.dispatch import receiver
from users.models import TelegramUser


class Broadcast(models.Model):
    """
    16-bosqich: admin global yoki tanlab (segment) e'lon jo'natadi.
    Yuborish jarayoni Celery task orqali background da bajariladi (rate-limitga tushmaslik uchun).
    """

    class TargetType(models.TextChoices):
        ALL = "all", "Barcha foydalanuvchilar"
        ACTIVE_SUBSCRIBERS = "active_subscribers", "Faol obunachilar"
        EXPIRED_SUBSCRIBERS = "expired_subscribers", "Muddati tugaganlar"
        SPECIFIC_PLAN = "specific_plan", "Muayyan tarif obunachilari"
        CUSTOM_LIST = "custom_list", "Qo'lda tanlangan foydalanuvchilar"

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        SCHEDULED = "scheduled", "Rejalashtirilgan"
        QUEUED = "queued", "Navbatga qo'yilgan"
        SENDING = "sending", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xatolik"

    title = models.CharField(max_length=150, help_text="Faqat admin panel uchun, mijozga ko'rinmaydi")
    text = models.TextField()
    image = models.ImageField(upload_to="broadcasts/", blank=True, null=True)
    video = models.FileField(
        upload_to="broadcasts/videos/", blank=True, null=True,
        help_text="Ixtiyoriy video. 'Dumaloq video xabar' belgilansa, Telegram'da doira "
                   "shaklida (video note) yuboriladi — bunda kvadrat (1:1) va 60 soniyagacha bo'lishi tavsiya etiladi.",
    )
    is_video_note = models.BooleanField(
        default=False,
        help_text="Yoqilgan bo'lsa, video oddiy (to'rtburchak) emas, balki Telegramning "
                   "dumaloq video xabari (video note) sifatida yuboriladi",
    )
    image_file_id = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Qayta yuklamaslik uchun keshlangan Telegram file_id (rasm birinchi marta "
                   "yuborilgandan keyin avtomatik saqlanadi)",
    )
    video_file_id = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Qayta yuklamaslik uchun keshlangan Telegram file_id (video birinchi marta "
                   "yuborilgandan keyin avtomatik saqlanadi)",
    )
    scheduled_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Belgilansa, e'lon shu sana/vaqtda avtomatik yuboriladi (bo'sh bo'lsa — qo'lda yuborish kerak)",
    )

    button_text = models.CharField(
        max_length=64, blank=True, null=True,
        help_text="Ixtiyoriy inline tugma matni (masalan: 'Batafsil'). Bo'sh bo'lsa tugma chiqmaydi.",
    )
    button_url = models.URLField(
        blank=True, null=True,
        help_text="Ixtiyoriy inline tugma bosilganda ochiladigan havola",
    )

    target_type = models.CharField(max_length=30, choices=TargetType.choices, default=TargetType.ALL)
    target_plan = models.ForeignKey(
        "subscriptions.SubscriptionPlan", on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Faqat target_type=specific_plan bo'lsa ishlatiladi",
    )
    custom_users = models.ManyToManyField(TelegramUser, blank=True, related_name="custom_broadcasts")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"

    def __str__(self):
        return self.title


@receiver(models.signals.pre_save, sender=Broadcast)
def _invalidate_broadcast_file_id_on_change(sender, instance, **kwargs):
    """
    Admin rasm/videoni ALMASHTIRSA, eski faylga tegishli keshlangan `telegram file_id`
    endi noto'g'ri bo'lib qoladi (yangi faylga tegishli emas) — shu sababli fayl
    o'zgarganda mos file_id ham tozalanadi, aks holda bot eski faylni davom ettirib yuborar edi.
    """
    if not instance.pk:
        return
    try:
        old = Broadcast.objects.get(pk=instance.pk)
    except Broadcast.DoesNotExist:
        return
    if old.image != instance.image and instance.image_file_id == old.image_file_id:
        instance.image_file_id = None
    if old.video != instance.video and instance.video_file_id == old.video_file_id:
        instance.video_file_id = None


class BroadcastRecipient(models.Model):
    broadcast = models.ForeignKey(Broadcast, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE)
    is_sent = models.BooleanField(default=False)
    error = models.CharField(max_length=255, blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("broadcast", "user")