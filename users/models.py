from django.db import models


class TelegramUser(models.Model):
    """
    1-2-bosqich: mijoz botga kirganda yaratiladi.
    /start bosilganda avval shu obyekt get_or_create qilinadi,
    keyin ism va telefon so'raladi (registration_step orqali kuzatiladi).
    """

    class RegistrationStep(models.TextChoices):
        STARTED = "started", "Boshlandi"
        WAITING_NAME = "waiting_name", "Ism kutilmoqda"
        WAITING_PHONE = "waiting_phone", "Telefon kutilmoqda"
        COMPLETED = "completed", "Yakunlangan"

    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=64, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)  # mijoz kiritgan ism
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    registration_step = models.CharField(
        max_length=20, choices=RegistrationStep.choices, default=RegistrationStep.STARTED
    )

    # 15-bosqich uchun: qaysi step/menu holatida turibdi (FSM state saqlash uchun yordamchi)
    bot_state = models.CharField(max_length=64, blank=True, null=True)
    bot_state_data = models.JSONField(default=dict, blank=True)

    is_blocked_bot = models.BooleanField(default=False)  # mijoz botni block qilgan bo'lsa broadcastda tashlab ketish uchun

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Telegram foydalanuvchi"
        verbose_name_plural = "Telegram foydalanuvchilar"

    def __str__(self):
        return self.full_name or str(self.telegram_id)

    @property
    def is_registered(self):
        return self.registration_step == self.RegistrationStep.COMPLETED

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

