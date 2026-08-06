# JOYLASHTIRISH MANZILI: ACADEMY_BACK/subscriptions/models.py

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from users.models import TelegramUser


class SubscriptionPlan(models.Model):
    """
    3-bosqich: '1 oy - 99000 so'm / $9.9', '3 oy - 297000 so'm / $29.7'.
    Admin panel orqali to'liq boshqariladi (narx, muddat, tartib) -> matnlar shundan dinamik olinadi.
    """

    title = models.CharField(max_length=100, help_text="Masalan: 1 oylik obuna")
    duration_months = models.PositiveSmallIntegerField(help_text="Necha oyga obuna (to'lov davriyligi ham shu)")
    price_uzs = models.DecimalField(max_digits=12, decimal_places=2)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, help_text="Chet eldan (Tribute) narxi")
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0, help_text="Tugmalar tartibi")

    class Meta:
        ordering = ["position"]
        verbose_name = "Obuna tarifi"
        verbose_name_plural = "Obuna tariflari"

    def __str__(self):
        return f"{self.title} — {self.price_uzs} so'm / ${self.price_usd}"


class PaymentCard(models.Model):
    """
    5 va 15-bosqich: Payme orqali bog'langan karta (recurring uchun token saqlanadi).
    Tribute uchun karta ma'lumoti bizda emas, faqat external_subscription_id saqlanadi (Subscription da).
    """

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="cards")
    masked_pan = models.CharField(max_length=25, help_text="561468******7403 ko'rinishida")
    payme_card_token = models.CharField(max_length=255, help_text="Payme create-card tokeni (maxfiy, faqat backend ishlatadi)")
    is_primary = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bog'langan karta"
        verbose_name_plural = "Bog'langan kartalar"

    def __str__(self):
        return f"{self.user} — {self.masked_pan}"


class Subscription(models.Model):
    """
    Mijozning joriy/tarixiy obunasi. Har safar to'lov qilinganda yoki tarif o'zgarganda
    yangi Subscription yozuvi emas — mavjudi yangilanadi (uzluksiz streak uchun gifts appida
    kuzatiladi). Bekor qilingan/tugagan obunalar tarixi Payment orqali ko'rinadi.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "To'lov kutilmoqda"
        ACTIVE = "active", "Faol"
        CANCELLED = "cancelled", "Avto to'lov bekor qilingan (muddat oxirigacha faol)"
        EXPIRED = "expired", "Tugagan"

    class Provider(models.TextChoices):
        PAYME = "payme", "Payme (Uzcard/Humo)"
        TRIBUTE = "tribute", "Tribute (chet eldan)"

    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=20, choices=Provider.choices)

    locked_price_uzs = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text=(
            "Mijoz shu obunani (yoki qayta obunani) sotib olgan paytdagi Payme narxi — "
            "'muzlatilgan' narx. Keyingi barcha avto to'lovlar (kaskad) shu qiymatdan "
            "yechiladi, hatto admin panelda tarif narxi (`SubscriptionPlan.price_uzs`) "
            "keyinchalik oshirilgan/tushirilgan bo'lsa ham — mijoz obuna shartlarini "
            "buzmaguncha (bekor qilib/muddati tugab qayta sotib olguncha) shu narxda "
            "qolaveradi. Mijoz qaytadan (yangidan) sotib olganda bu qiymat joriy narx "
            "bilan qayta yozib qo'yiladi. Bo'sh (`null`) bo'lsa — bu maydon qo'shilishidan "
            "OLDIN yaratilgan eski obuna, xavfsizlik uchun joriy plan narxiga tushiladi."
        ),
    )
    locked_price_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Xuddi shu mantiq — chet eldan (Tribute) narxi uchun.",
    )

    card = models.ForeignKey(PaymentCard, on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriptions")
    tribute_external_id = models.CharField(max_length=255, blank=True, null=True)

    started_at = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateField(null=True, blank=True, db_index=True)
    auto_renew = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Obuna"
        verbose_name_plural = "Obunalar"

    def __str__(self):
        return f"{self.user} — {self.plan} — {self.get_status_display()}"


class Payment(models.Model):
    """
    Har bir muvaffaqiyatli/muvaffaqiyatsiz to'lov shu yerda logланади.
    6-bosqich mantig'i: 1 oylik plan -> har oy Payment yaratiladi;
    3 oylik plan -> har 3 oyda bitta Payment yaratiladi (cron shu jadvaldan next_payment_date ni hisoblaydi).
    """

    class Status(models.TextChoices):
        SUCCESS = "success", "Muvaffaqiyatli"
        FAILED = "failed", "Muvaffaqiyatsiz"
        PENDING = "pending", "Kutilmoqda"

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="UZS")
    provider = models.CharField(max_length=20, choices=Subscription.Provider.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    external_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    is_recurring_charge = models.BooleanField(default=False, help_text="False = mijoz o'zi to'lagan birinchi to'lov")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        constraints = [
            # Dastur darajasidagi idempotentlik tekshiruviga (subscription_service.py) qo'shimcha
            # SO'NGGI himoya chizig'i: bir xil provayder + bir xil tashqi tranzaksiya id bilan
            # ikkinchi Payment yaratilishiga DB darajasida yo'l qo'yilmaydi (masalan Tribute
            # webhookining dublikat yetkazilishi natijasida ikkita parallel so'rov bir vaqtda
            # kelib qolsa ham). Bo'sh/mavjud bo'lmagan external_transaction_id'lar bundan
            # mustasno (Payme'ning ba'zi eski PENDING/FAILED yozuvlarida bo'lmasligi mumkin).
            models.UniqueConstraint(
                fields=["provider", "external_transaction_id"],
                condition=~models.Q(external_transaction_id=None) & ~models.Q(external_transaction_id=""),
                name="unique_provider_external_transaction_id",
            ),
        ]

    def __str__(self):
        return f"{self.subscription.user} — {self.amount} {self.currency} — {self.status}"


class SubscriptionRenewalCycle(models.Model):
    """
    17-18-bosqich markazi: har bir to'lov davri (billing cycle) uchun BITTA yozuv.
    Barcha qayta urinishlar shu obyekt atrofida, DB darajasidagi qulf (select_for_update)
    bilan boshqariladi — shu orqali 'mijozdan faqat bir marta pul yechilishi, bir necha marta
    yechib ketmasligi' (18-bosqich) kafolatlanadi: har bir urinish avval joriy holatni
    tekshiradi, agar bu davr allaqachon SUCCEEDED yoki CANCELLED bo'lsa — hech narsa qilmay chiqib ketadi.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Navbatda"
        IN_PROGRESS = "in_progress", "Yechilmoqda (qulflangan)"
        AWAITING_USER = "awaiting_user", "Mijoz kutilmoqda ('Davom etish')"
        AWAITING_CARD_UPDATE = "awaiting_card_update", "Karta yangilanishi kutilmoqda"
        SUCCEEDED = "succeeded", "Muvaffaqiyatli yakunlandi"
        CANCELLED = "cancelled", "Obuna to'xtatildi"

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="renewal_cycles")
    due_date = models.DateField(help_text="Ushbu billing davri uchun to'lov sanasi (Subscription.next_payment_date qiymati shu kunga teng bo'lganda yaratiladi)")
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.SCHEDULED)

    attempt_number = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True, help_text="IN_PROGRESS holatiga o'tgan vaqt — stale-lock aniqlash uchun")

    last_result = models.CharField(max_length=30, blank=True, null=True)  # success / insufficient_funds / card_expired
    last_error_reason = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("subscription", "due_date")  # bitta billing davriga faqat bitta cycle
        verbose_name = "Obuna yangilash jarayoni"
        verbose_name_plural = "Obuna yangilash jarayonlari"

    def __str__(self):
        return f"{self.subscription.user} — {self.due_date} — {self.get_status_display()} (urinish {self.attempt_number})"

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.SUCCEEDED, self.Status.CANCELLED)


class RenewalAttempt(models.Model):
    """Har bir alohida to'lov urinishining tarixi — audit va nizolarni tekshirish uchun."""

    cycle = models.ForeignKey(SubscriptionRenewalCycle, on_delete=models.CASCADE, related_name="attempts")
    attempt_number = models.PositiveSmallIntegerField()
    result = models.CharField(max_length=30)  # success / insufficient_funds / card_expired / error
    error_reason = models.CharField(max_length=255, blank=True, null=True)
    payme_order_id = models.CharField(max_length=100, help_text="cycle_id+attempt_number asosida — idempotentlik uchun")
    payme_receipt_id = models.CharField(
        max_length=100, blank=True, null=True,
        help_text=(
            "Payme receipts.create javobidagi chek ID'si. Agar shu urinish 'error' bilan "
            "tugagan bo'lsa (masalan receipts.pay javobi tarmoq uzilishi sabab yetib kelmagan "
            "bo'lsa), keyingi urinishdan oldin receipts.check shu ID orqali tekshiriladi — "
            "pul haqiqatda allaqachon yechilgan bo'lsa, ikkinchi marta yechilmasligi uchun."
        ),
    )
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cycle", "attempt_number")  # bir xil urinish raqami ikki marta yozilmasin
        ordering = ["attempt_number"]
        verbose_name = "To'lov urinishi"
        verbose_name_plural = "To'lov urinishlari"

    def __str__(self):
        return f"{self.cycle} — urinish #{self.attempt_number} — {self.result}"


class PaymentReminderLog(models.Model):
    """
    17-bosqich: 3/2/1 kunlik eslatmalar va SMS bir kunda faqat bir marta yuborilishini
    kafolatlaydigan dedupe jadvali (background task soat sayin ishga tushsa ham qayta yubormaydi).
    """

    class ReminderType(models.TextChoices):
        DAYS_BEFORE = "days_before", "N kun oldin (bot)"
        SMS_DAY_BEFORE = "sms_day_before", "SMS eslatma"

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="reminder_logs")
    due_date = models.DateField()
    reminder_type = models.CharField(max_length=20, choices=ReminderType.choices)
    days_before = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("subscription", "due_date", "reminder_type", "days_before")
        verbose_name = "Eslatma jurnali"
        verbose_name_plural = "Eslatmalar jurnali"


class PendingCheckout(models.Model):
    """
    4-bosqich: mijoz tarif va to'lov usulini tanlagandan so'ng, lekin to'lov tugamasdan turib
    holatni saqlab turish uchun. Payme/Tribute webhook kelganda shu yozuv orqali qaysi
    user/plan/provider ekanligi aniqlanadi (referal havoladagi `pay` parametri shu jadvalning id/uuid siga bog'lanadi).
    """

    checkout_uuid = models.UUIDField(unique=True)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="pending_checkouts")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=Subscription.Provider.choices)
    purpose = models.CharField(
        max_length=25,
        choices=[
            ("new_subscription", "Yangi obuna"),
            ("card_change", "Kartani almashtirish (oddiy)"),
            ("renewal_card_update", "Kartani almashtirish (to'lov kaskadi ichida)"),
        ],
        default="new_subscription",
    )
    renewal_cycle = models.ForeignKey(
        "SubscriptionRenewalCycle", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="card_update_checkouts",
        help_text="Faqat purpose=renewal_card_update bo'lganda to'ldiriladi — karta yangilangach shu cycle qayta urinadi",
    )
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    # pay.turdievakademiyasi.uz form oqimi uchun (Payme Cards API, 2-bosqichli: create -> verify).
    # DIQQAT: xom karta raqami (PAN) hech qachon bu yerga yoki boshqa hech qanday jadvalga
    # yozilmaydi — faqat Payme cards.create javobidagi token va masklangan raqam saqlanadi,
    # va faqat verify muvaffaqiyatli bo'lgandan keyin PaymentCard ga ko'chiriladi.
    pending_card_token = models.CharField(max_length=255, blank=True, null=True)
    pending_masked_pan = models.CharField(max_length=25, blank=True, null=True)
    verify_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "To'lov jarayoni (vaqtinchalik)"
        verbose_name_plural = "To'lov jarayonlari (vaqtinchalik)"

    def __str__(self):
        return f"{self.checkout_uuid} — {self.user} — {self.provider}"


class RenewalSettings(models.Model):
    """
    Avto-to'lov jarayonining VAQT sozlamalari (necha kun oldin eslatma, muvaffaqiyatsiz
    urinishdan keyin necha soatdan keyin qayta urinilsin, jami nechta urinish) — admin
    panel orqali tahrirlanadi.

    MUHIM CHEGARA (18-bosqichdagi to'lov xavfsizligi buzilmasligi uchun ataylab shunday
    loyihalangan):
      - Bu yerda faqat VAQT/SON o'zgaradi — QAYSI xabar (slug) qachon yuborilishi hamon
        `bot/services/renewal_notifier.py`dagi BOSQICH raqami (1/2/3/4) bo'yicha qattiq
        belgilangan, kun/soat QIYMATI bo'yicha emas. Shu sabab admin "3 kun"ni "5 kun"ga
        o'zgartirsa ham, tegishli bot matni (masalan "renewal_reminder_3d") baribir to'g'ri
        topiladi — hech qanday xabar "yo'qolib qolmaydi".
      - To'lov summasi (`plan.price_uzs`) va ikki marta pul yechilmasligini kafolatlaydigan
        claim/idempotency mexanizmi (`renewal_engine.py`) bu sozlamalarga UMUMAN bog'liq
        emas — faqat QACHON keyingi urinish REJALASHTIRILISHI shu yerdan olinadi.
      - Faqat BITTA qator bo'ladi (singleton) — `RenewalSettings.load()` orqali olinadi.
    """

    reminder_stage_1_days = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="1-eslatma ('renewal_reminder_3d' matni) to'lov sanasidan necha kun oldin yuborilsin.",
    )
    reminder_stage_2_days = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="2-eslatma ('renewal_reminder_2d' matni) to'lov sanasidan necha kun oldin yuborilsin.",
    )
    reminder_stage_3_days = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="3-eslatma ('renewal_reminder_1d' matni) to'lov sanasidan necha kun oldin yuborilsin.",
    )
    sms_on_stage = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(0), MaxValueValidator(3)],
        help_text="Qaysi eslatma bosqichida (1/2/3) SMS ham yuborilsin. 0 = SMS o'chirilgan.",
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Avto-to'lov vaqt sozlamalari"
        verbose_name_plural = "Avto-to'lov vaqt sozlamalari"

    def __str__(self):
        return "Avto-to'lov vaqt sozlamalari"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RenewalRetryStage(models.Model):
    """
    Avto-to'lov muvaffaqiyatsiz-urinishlar zanjiridagi DINAMIK bosqich.

    ESKI ARXITEKTURA: qayta urinish oralig'i `RenewalSettings`dagi 4 ta QATTIQ
    maydon edi (`retry_wait_hours_stage_1..4`), `max_attempts` esa 2-8 oralig'ida
    cheklangan alohida son edi. Natijada: (1) admin 4 tadan ortiq HAQIQIY (o'ziga
    xos soatli) qayta urinish belgilay olmasdi — 4-dan keyingi hamma urinishlar
    4-bosqich soatini "meros" qilib olardi (`renewal_engine.py`dagi
    `min(current_attempt, 4)`); (2) "nechta urinish" va "har biri necha soatdan"
    ikkita bir-biriga bog'liq bo'lmagan sozlama edi — admin ularni mos ravishda
    sinxron ushlab turishi kerak edi.

    YANGI: har bir qator — "N-urinish muvaffaqiyatsiz bo'lsa, (N+1)-urinishgacha
    necha soat kutilsin" degan ma'noni bildiradi. Admin istalgan sondagi qator
    qo'sha/o'chira oladi (`RenewalRetryStageViewSet.create`/`destroy`) — shu bilan
    "nechta urinish" ENDI shu jadvaldagi qatorlar soni + 1 sifatida avtomatik
    hisoblanadi (`max_attempts()`), alohida sinxronlashtiriladigan son emas.

    Yangi qator qo'shilganda backend avtomatik ravishda shu `attempt_number`ga
    bog'langan CUSTOM bot xabarini ham yaratadi (`cms.BotMessageTemplate`,
    group='renewal_fail_cascade', trigger_event='attempt') — shunda admin
    darhol Bot xabarlari konstruktorida shu urinish uchun matn yoza oladi,
    alohida "endi bot xabarlar bo'limiga o'zim qo'shib qo'yay" qadamisiz.
    """

    attempt_number = models.PositiveSmallIntegerField(
        unique=True, validators=[MinValueValidator(1)],
        help_text="Ushbu urinish (masalan 1, 2, 3...) muvaffaqiyatsiz bo'lsa, keyingisigacha necha soat kutilishi haqida.",
    )
    wait_hours = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(240)],
        help_text="Shu urinish muvaffaqiyatsiz bo'lsa, keyingi urinishgacha necha soat kutilsin.",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Avto-to'lov qayta urinish bosqichi"
        verbose_name_plural = "Avto-to'lov qayta urinish bosqichlari"
        ordering = ["attempt_number"]

    def __str__(self):
        return f"{self.attempt_number}-urinish muvaffaqiyatsiz -> {self.wait_hours} soat kutish"

    @classmethod
    def ensure_seeded(cls):
        """Bazada birorta ham qator bo'lmasa (masalan birinchi marta ishga tushirilganda),
        zavod standart qiymatlari bilan to'ldiradi — bot hech qachon shu sabab yiqilib
        qolmaydi, admin panel ham bo'sh holatda ochilmaydi."""
        if cls.objects.exists():
            return
        from subscriptions.renewal_config import DEFAULT_RETRY_WAIT_HOURS

        cls.objects.bulk_create(
            [cls(attempt_number=n, wait_hours=h) for n, h in sorted(DEFAULT_RETRY_WAIT_HOURS.items())]
        )

    @classmethod
    def max_attempts(cls) -> int:
        """Jami urinishlar soni = qayta urinish bosqichlari soni + 1 (dastlabki urinish)."""
        cls.ensure_seeded()
        return cls.objects.count() + 1

    @classmethod
    def wait_hours_for(cls, attempt_number: int) -> int:
        """`attempt_number`-urinish uchun kutish soati. Ro'yxatda aynan shu raqamga mos
        qator topilmasa (masalan admin oxirgi bosqichni endigina o'chirgan bo'lsa-yu,
        eski rejalashtirilgan celery task hali navbatda tursa), ENG YAQIN pastroq
        qatorning qiymati ishlatiladi — tizim hech qachon xatolik bilan yiqilmaydi."""
        cls.ensure_seeded()
        stage = cls.objects.filter(attempt_number__lte=attempt_number).order_by("-attempt_number").first()
        if stage:
            return stage.wait_hours
        first = cls.objects.order_by("attempt_number").first()
        if first:
            return first.wait_hours
        from subscriptions.renewal_config import DEFAULT_RETRY_WAIT_HOURS

        return DEFAULT_RETRY_WAIT_HOURS[max(DEFAULT_RETRY_WAIT_HOURS)]