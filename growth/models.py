# JOYLASHTIRISH MANZILI: ACADEMY_BACK/growth/models.py

from django.conf import settings
from django.db import models


class AdmissionSettings(models.Model):
    """
    Qabulni boshqarish (singleton, faqat bitta qator bo'ladi — `AdmissionSettings.load()`
    orqali olinadi).

    - `is_open=False` bo'lsa, botga YANGI kelgan (hali ro'yxatdan o'tmagan/tugatmagan)
      foydalanuvchilarga ro'yxatdan o'tish/taklif oqimi o'rniga "qabul yopiq" xabari
      ko'rsatiladi (`cms.bot_texts` dagi "admission_closed" slug).
    - Bu holat allaqachon ro'yxatdan o'tgan/obunasi bor ishtirokchilarga TA'SIR QILMAYDI —
      ular botdan odatdagidek foydalanishda davom etadi.
    - `allow_referral_when_closed=True` bo'lsa, qabul yopiq bo'lsa ham, FAOL referal
      havola (`ReferralLink.is_active=True`) orqali kirgan yangi foydalanuvchilar
      baribir ro'yxatdan o'tishi mumkin — shu orqali maqsadli reklama kampaniyasi uchun
      qabulni alohida ochiq qoldirish mumkin, umumiy oqim esa yopiq turadi.
    """

    is_open = models.BooleanField(default=True, help_text="Yangi foydalanuvchilar uchun qabul umuman ochiqmi")
    allow_referral_when_closed = models.BooleanField(
        default=True,
        help_text="Qabul yopiq bo'lsa ham, faol referal havolalar orqali kirganlar uchun ochiq qolsinmi",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Qabul sozlamalari"
        verbose_name_plural = "Qabul sozlamalari"

    def __str__(self):
        return "Qabul sozlamalari"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    async def aload(cls):
        obj, _ = await cls.objects.aget_or_create(pk=1)
        return obj


class ReferralLink(models.Model):
    """
    Reklama kampaniyalari uchun alohida havola: `t.me/<bot>?start=<code>`. Bot shu
    kod bilan kirgan HAR BIR yangi foydalanuvchini (birinchi marta) `leads_count`ga,
    birinchi muvaffaqiyatli to'lovini esa `sales_count`ga qo'shadi — shu orqali har bir
    reklama manbai (masalan YouTube video) qancha lid va sotuv keltirganini alohida
    ko'rish mumkin.
    """

    code = models.SlugField(max_length=50, unique=True, help_text="Masalan: VSL1 — havolada ?start=VSL1 ko'rinishida ishlatiladi")
    label = models.CharField(max_length=150, help_text="Ichki nom, masalan: YouTube — VSL 1-video")
    is_active = models.BooleanField(
        default=True,
        help_text="O'chirilsa, bu havola orqali yangi foydalanuvchi ro'yxatdan o'ta olmaydi (qabul umumiy holatiga bo'ysunadi)",
    )
    leads_count = models.PositiveIntegerField(default=0, help_text="Shu havola orqali botga kirgan yangi (unikal) foydalanuvchilar soni")
    sales_count = models.PositiveIntegerField(default=0, help_text="Shu havola orqali kelib birinchi marta to'lov qilganlar soni")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Referal havola"
        verbose_name_plural = "Referal havolalar"

    def __str__(self):
        return f"{self.label} ({self.code})"

    @property
    def start_link(self) -> str:
        username = settings.TELEGRAM_BOT_USERNAME
        if not username:
            return ""
        return f"https://t.me/{username}?start={self.code}"