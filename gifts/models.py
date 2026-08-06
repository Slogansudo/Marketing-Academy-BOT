from django.db import models
from users.models import TelegramUser


class GiftMonth(models.Model):
    """
    9-bosqich: 'Obuna jarayoni' bloki (11-rasm). Admin xohlagancha oy qo'sha oladi (12, 14, 15...).
    Har oy uchun: tier nomi (Boshlovchi/O'quvchi/Talaba...), sovg'a nomi, rasmi va olish havolasi.
    """

    month_number = models.PositiveSmallIntegerField(unique=True, help_text="1, 2, 3 ... ketma-ketlik muhim")
    tier_name = models.CharField(max_length=50, help_text="Masalan: Boshlovchi, O'quvchi, Talaba")
    gift_name = models.CharField(max_length=150, help_text="Masalan: Davron Turdiev Neyro boti")
    gift_image = models.ImageField(upload_to="gifts/", blank=True, null=True)
    claim_link = models.URLField(help_text="Sovg'ani olish uchun tashqi havola")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["month_number"]
        verbose_name = "Oylik sovg'a"
        verbose_name_plural = "Oylik sovg'alar"

    def __str__(self):
        return f"{self.month_number}-oy — {self.gift_name}"


class UserGiftProgress(models.Model):
    """
    Mijozning uzluksiz to'lov streaki. Har muvaffaqiyatli to'lovdan keyin cron/webhook
    orqali current_streak +1 qilinadi. To'lov o'tkazib yuborilsa (subscription EXPIRED bo'lsa)
    current_streak 0 ga tushiriladi — 'zinapoyadan qulash' logikasi shu yerda.
    """

    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name="gift_progress")
    current_streak_months = models.PositiveSmallIntegerField(default=0)
    highest_streak_months = models.PositiveSmallIntegerField(default=0)
    streak_broken_count = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sovg'a jarayoni"
        verbose_name_plural = "Sovg'a jarayonlari"

    def __str__(self):
        return f"{self.user} — {self.current_streak_months}-oy"

    def register_successful_payment(self):
        self.current_streak_months += 1
        self.highest_streak_months = max(self.highest_streak_months, self.current_streak_months)
        self.save(update_fields=["current_streak_months", "highest_streak_months", "updated_at"])

    def reset_streak(self):
        if self.current_streak_months > 0:
            self.streak_broken_count += 1
        self.current_streak_months = 0
        self.save(update_fields=["current_streak_months", "streak_broken_count", "updated_at"])


class UserGiftClaim(models.Model):
    """
    Sovg'a bosilganda (OLISH tugmasi) shu yerga yoziladi — takroriy anketa to'ldirmaslik uchun
    tizim buni tekshiradi va oldin to'ldirilgan bo'lsa, havolaga forma parametrlarisiz/"already_submitted"
    belgisi bilan yuboradi.
    """

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="gift_claims")
    gift_month = models.ForeignKey(GiftMonth, on_delete=models.CASCADE, related_name="claims")
    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "gift_month")
        verbose_name = "Sovg'a olingani"
        verbose_name_plural = "Sovg'a olinganlar"

    def __str__(self):
        return f"{self.user} — {self.gift_month}"
