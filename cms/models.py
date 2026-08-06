# JOYLASHTIRISH MANZILI: ACADEMY_BACK/cms/models.py

import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .bot_texts import BOT_MESSAGE_GROUPS
from .funnel import TriggerEvent


class BotMessageTemplate(models.Model):
    """
    Bot xabarlarining TAHRIRLANADIGAN matni/sarlavhasi — admin panel konstruktori
    shu model orqali ishlaydi.

    MUHIM CHEGARA (o'zgardi — 2-avlod dinamik voronka): `group` (kategoriya)
    hamon kod tomonidan belgilangan haqiqiy ulanish nuqtasini anglatadi — yangi
    kategoriya admin panel orqali qo'shilmaydi. LEKIN har bir kategoriya ICHIDA
    endi qatorlar to'liq dinamik: `step_type=CORE` qatorlar (`cms.bot_texts.BOT_TEXTS`
    dagi mavjud slug'lar — kod ichida haqiqiy chaqiriladigan nuqtalar) hamon
    o'chirilmaydi, lekin `step_type=CUSTOM` qatorlarni admin konstruktor orqali
    ISTALGAN songacha qo'sha oladi, o'chira oladi va guruh ichida tartiblay oladi —
    bular kodga bog'liq bo'lmagan qo'shimcha xabarlar (masalan ikkita CORE qadam
    orasiga qo'yiladigan bonus/eslatma xabari). Bot xizmat qatlami endi "shu
    slug'ni yubor" emas, balki "shu kategoriyaning barcha faol qadamlarini
    pozitsiya bo'yicha ketma-ket yubor" tarzida ishlaydi (qarang: `cms/funnel.py`).
    """

    class Group(models.TextChoices):
        ONBOARDING = "onboarding", "Ro'yxatdan o'tish"
        PAYMENT = "payment", "Taklif va to'lov"
        MAIN_MENU = "main_menu", "Asosiy menyu va obuna holati"
        RENEWAL_REMINDERS = "renewal_reminders", "Avto-to'lov — eslatmalar"
        RENEWAL_FAIL_CASCADE = "renewal_fail_cascade", "Avto-to'lov — muvaffaqiyatsiz urinishlar"
        ADMISSION = "admission", "Qabul yopiq xabari"

    class StepType(models.TextChoices):
        CORE = "core", "Tizim bosqichi (kod bilan bog'langan)"
        CUSTOM = "custom", "Qo'shimcha xabar (admin qo'shgan)"

    # "Eslatmalar" guruhi (3 kun/2 kun/1 kun qoldi) uchtasi ham mustaqil,
    # kalendar-sanaga bog'langan alohida triggerlar — ular orasida "ketma-ket
    # ro'yxat" ma'nosi yo'q, shuning uchun pozitsiyasi hamon qulflangan.
    # "Muvaffaqiyatsiz urinishlar" guruhi endi `attempt_number`/`trigger_event`
    # orqali boshqariladi (pastga qarang) — shu sabab bu yerdan chiqarib
    # tashlandi, u yerda pozitsiya faqat BIR XIL urinish/hodisaga tegishli bir
    # nechta xabar orasidagi tartibni bildiradi va admin tomonidan erkin.
    POSITION_LOCKED_GROUPS = {"renewal_reminders"}

    # Faqat shu guruhda ma'noli: har bir qadam qaysi urinish/hodisaga
    # bog'langanini bildiruvchi maydonlar (`trigger_event`, `attempt_number`).
    CASCADE_GROUP = "renewal_fail_cascade"

    slug = models.SlugField(
        unique=True,
        help_text=(
            "CORE qatorlar uchun — qaysi statik bot xabari (kod nuqtasi). "
            "CUSTOM qatorlar uchun — avtomatik generatsiya qilinadi."
        ),
    )
    group = models.CharField(max_length=30, choices=Group.choices, db_index=True)
    step_type = models.CharField(
        max_length=10, choices=StepType.choices, default=StepType.CORE, db_index=True,
        help_text="CORE — kod bilan bog'langan, o'chirilmaydi. CUSTOM — admin qo'shgan qo'shimcha xabar.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="O'chirilgan bo'lsa, bu xabar yuborilmaydi (o'chirib tashlamasdan vaqtincha to'xtatish uchun).",
    )
    trigger_event = models.CharField(
        max_length=30, choices=TriggerEvent.choices, blank=True, null=True,
        help_text=(
            "Faqat 'Avto-to'lov — muvaffaqiyatsiz urinishlar' toifasida ishlatiladi: "
            "bu qadam qaysi haqiqiy hodisada ishga tushishi."
        ),
    )
    attempt_number = models.PositiveSmallIntegerField(
        blank=True, null=True,
        help_text="Faqat trigger_event='attempt' bo'lsa: nechinchi muvaffaqiyatsiz urinishda yuborilsin.",
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Admin konstruktoridagi kartochka tartibi (guruh ichida, yoki kaskad guruhida — "
            "bitta urinish/hodisa ichida bir nechta xabar bo'lsa, ular orasidagi tartib)."
        ),
    )

    title = models.CharField(max_length=150, help_text="Faqat admin panelda ko'rinadi, mijozga yuborilmaydi")
    text = models.TextField(help_text="Mijozga yuboriladigan joriy matn")
    default_text = models.TextField(help_text="Zavod sozlamasi (kod ichidagi asl matn) — 'Asliga qaytarish' uchun")

    placeholders = models.JSONField(
        default=list, blank=True,
        help_text="Ushbu matnda ishlatilishi mumkin bo'lgan {placeholder} nomlari (avtomatik aniqlangan, faqat ma'lumot uchun)",
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="Yoqilgan bo'lsa, faqat superuser tahrirlay oladi (masalan oferta/rozilik matni bor xabarlar)",
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Bot xabari (tahrirlanadigan)"
        verbose_name_plural = "Bot xabarlari (tahrirlanadigan)"
        ordering = ["group", "position", "slug"]

    def __str__(self):
        return f"{self.title} ({self.slug})"

    @property
    def position_locked(self):
        return self.group in self.POSITION_LOCKED_GROUPS

    def clean(self):
        """Dinamik voronka qoidalarini tekshiradi (serializer va viewsetning create/update oqimida chaqiriladi)."""
        errors = {}
        if self.step_type == self.StepType.CORE:
            if self.slug not in BOT_MESSAGE_GROUPS:
                errors["slug"] = "CORE turidagi qator faqat kod ichida mavjud slug'larga tegishli bo'lishi mumkin."
            expected_group = BOT_MESSAGE_GROUPS.get(self.slug)
            if expected_group and self.group != expected_group:
                errors["group"] = "Bu tizim bosqichi doimiy ravishda boshqa toifaga tegishli - uni o'zgartirib bo'lmaydi."
        elif not self.slug:
            self.slug = "custom_" + uuid.uuid4().hex[:10]
        if self.group == self.CASCADE_GROUP:
            if self.trigger_event == TriggerEvent.ATTEMPT and not self.attempt_number:
                errors["attempt_number"] = "trigger_event='attempt' bo'lsa, urinish raqami ko'rsatilishi shart."
            elif self.trigger_event and self.trigger_event != TriggerEvent.ATTEMPT and self.attempt_number:
                errors["attempt_number"] = "Bu hodisa turi urinish raqamiga bog'liq emas."
            elif not self.trigger_event and self.step_type == self.StepType.CUSTOM:
                errors["trigger_event"] = "Avto-to'lov kaskadida yangi xabar qaysi hodisaga tegishli ekani ko'rsatilishi shart."
        elif self.trigger_event or self.attempt_number:
            errors["trigger_event"] = "trigger_event/attempt_number faqat avto-to'lov kaskadi toifasida ishlatiladi."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.group:
            self.group = BOT_MESSAGE_GROUPS.get(self.slug, self.Group.MAIN_MENU)
        if self.step_type == self.StepType.CUSTOM and not self.slug:
            self.slug = "custom_" + uuid.uuid4().hex[:10]
        self.placeholders = sorted(set(re.findall(r"\{(\w+)\}", self.text or "")))
        super().save(*args, **kwargs)


@receiver(post_save, sender=BotMessageTemplate)
@receiver(post_delete, sender=BotMessageTemplate)
def _invalidate_bot_text_cache(sender, **kwargs):
    from .bot_texts import invalidate_bot_text_cache

    invalidate_bot_text_cache()


class FunnelCategorySettings(models.Model):
    """
    Bot xabarlari konstruktoridagi kategoriya (bo'lim) larning EKRANDA
    ko'rsatilish tartibi (masalan "Asosiy menyu" bo'limini "Taklif va
    to'lov"dan yuqoriroq ko'rsatish). Admin buni o'zgartira oladi, lekin
    faqat `cms.funnel.CATEGORY_DEPENDENCIES` bog'liqligini buzmaydigan
    tarzda — bu qoida saqlashda emas, balki serializer/viewset darajasida
    (`cms.funnel.validate_category_order`) tekshiriladi, chunki bir nechta
    qatorni birgalikda tekshirish kerak.
    """

    category = models.CharField(max_length=30, choices=BotMessageTemplate.Group.choices, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Voronka kategoriya tartibi"
        verbose_name_plural = "Voronka kategoriya tartiblari"
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.get_category_display()} (#{self.sort_order})"

    @classmethod
    def ensure_seeded(cls):
        """Har bir mavjud kategoriya uchun qator borligiga ishonch hosil qiladi
        (dastlab BotMessageTemplate.Group.choices tartibida)."""
        for index, (key, _label) in enumerate(BotMessageTemplate.Group.choices):
            cls.objects.get_or_create(category=key, defaults={"sort_order": index})

    @classmethod
    def current_order(cls) -> list[str]:
        cls.ensure_seeded()
        return list(cls.objects.order_by("sort_order").values_list("category", flat=True))


class BotMedia(models.Model):
    """
    Bot xabarlarining matni endi statik (kodda, `cms.bot_texts`) — bu yerda faqat
    o'sha ro'yxatdagi istalgan xabarga (slug) biriktiriladigan media saqlanadi.
    Bitta statik xabarga eng ko'pi bilan bitta media biriktirilishi mumkin (`slug` unique).

    Media istalgan turdagi bo'lishi mumkin (`media_type`): video, audio yoki rasm — bot
    shunga mos Telegram metodi (sendVideo/sendAudio/sendPhoto) bilan yuboradi. Video uchun
    qo'shimcha ravishda shakl (`video_shape`) tanlanadi: oddiy to'rtburchak yoki Telegramning
    dumaloq "video xabar" (video note) formati.

    MUHIM (2-avlod dinamik voronka): `slug` endi statik `BOT_MESSAGE_CHOICES` ro'yxati
    bilan CHEKLANMAYDI — CUSTOM xabarlar (admin konstruktorda qo'shgan, avtomatik
    generatsiya qilingan `custom_xxxxxxxxxx` slug'lar) ham media biriktira olishi kerak.
    Buning o'rniga `clean()` orqali slug haqiqatan ham mavjud `BotMessageTemplate`ga
    tegishli ekani tekshiriladi.
    """

    class MediaType(models.TextChoices):
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        PHOTO = "photo", "Rasm"

    class VideoShape(models.TextChoices):
        RECTANGLE = "rectangle", "To'rtburchak (oddiy video)"
        CIRCLE = "circle", "Dumaloq (video xabar)"

    slug = models.SlugField(
        unique=True,
        help_text="Qaysi bot xabariga (BotMessageTemplate.slug — CORE yoki CUSTOM) biriktirilgan",
    )
    media_type = models.CharField(
        max_length=10, choices=MediaType.choices, default=MediaType.VIDEO,
        help_text="Qanday turdagi media — botda shu turga mos Telegram metodi bilan yuboriladi",
    )
    video_shape = models.CharField(
        max_length=10, choices=VideoShape.choices, default=VideoShape.RECTANGLE, blank=True,
        help_text=(
            "Faqat media_type=video bo'lsa ma'noli. 'Dumaloq' — Telegramning video-xabar "
            "(video note) formati; bu faqat yuklangan faylga ishlaydi, tashqi URL'ga emas, "
            "va caption (matn) qo'llab-quvvatlanmaydi — matn video ostida alohida xabar sifatida ketadi."
        ),
    )
    file = models.FileField(
        upload_to="bot_media/", blank=True, null=True,
        help_text="Yuklangan media fayl (video/audio/rasm)",
    )
    video_url = models.URLField(
        blank=True, null=True,
        help_text="Fayl o'rniga tashqi video URL/Telegram file_id (faqat media_type=video, dumaloq shakl uchun ishlamaydi)",
    )
    telegram_file_id = models.CharField(max_length=255, blank=True, null=True, help_text="Qayta yuklamaslik uchun keshlangan file_id")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bot media"
        verbose_name_plural = "Bot medialari"

    def __str__(self):
        template = BotMessageTemplate.objects.filter(slug=self.slug).first()
        return template.title if template else self.slug

    def clean(self):
        if self.slug and not BotMessageTemplate.objects.filter(slug=self.slug).exists():
            raise ValidationError({"slug": "Bu slug'ga mos bot xabari (BotMessageTemplate) topilmadi."})

    @property
    def is_circle_video(self) -> bool:
        """Dumaloq video (video note) sifatida yuborilishi kerakmi. Faqat yuklangan fayl
        uchun ishlaydi — Telegram video-note tashqi URL'ni qo'llab-quvvatlamaydi."""
        return bool(self.media_type == self.MediaType.VIDEO and self.video_shape == self.VideoShape.CIRCLE and self.file)


@receiver(models.signals.pre_save, sender=BotMedia)
def _delete_old_botmedia_file_on_change(sender, instance, **kwargs):
    """
    Admin panel orqali media fayl ALMASHTIRILGANDA (yoki tashqi URL'ga o'tilganda),
    eski fayl serverdan (media papkasidan) o'chirib tashlanadi — orqasida ishlatilmay
    yotgan fayllar to'planib qolmasligi uchun. Eski faylga bog'langan telegram file_id
    keshi ham endi noto'g'ri bo'lgani sababli tozalanadi.
    """
    if not instance.pk:
        return
    try:
        old = BotMedia.objects.get(pk=instance.pk)
    except BotMedia.DoesNotExist:
        return
    if old.file and old.file != instance.file:
        old.file.delete(save=False)
        if instance.telegram_file_id == old.telegram_file_id:
            instance.telegram_file_id = None


@receiver(models.signals.post_delete, sender=BotMedia)
def _delete_botmedia_file_on_delete(sender, instance, **kwargs):
    """Media qatori butunlay o'chirilganda, biriktirilgan fayl ham diskdan o'chadi."""
    if instance.file:
        instance.file.delete(save=False)


class BotLink(models.Model):
    """
    Admin tomonidan o'zgartiriladigan barcha tashqi havolalar bir joyda:
    yopiq kanal, yordam, umumiy chat, offerta.
    """

    class Key(models.TextChoices):
        PRIVATE_CHANNEL = "private_channel", "Yopiq kanalga qo'shilish havolasi"
        HELP = "help", "Yordam havolasi"
        COMMUNITY_CHAT = "community_chat", "Umumiy chat havolasi"
        OFFER_DOCUMENT = "offer_document", "Oferta hujjati havolasi"

    key = models.CharField(max_length=30, choices=Key.choices, unique=True)
    url = models.URLField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bot havolasi"
        verbose_name_plural = "Bot havolalari"

    def __str__(self):
        return f"{self.get_key_display()} — {self.url}"


class ChannelSettings(models.Model):
    """
    Yopiq kanaldan avtomatik chiqarib yuborish uchun texnik sozlama (singleton).

    `BotLink.PRIVATE_CHANNEL` faqat kanalga QO'SHILISH havolasini (masalan
    t.me/+xxxxx) saqlaydi — bu Telegram Bot API orqali a'zoni chiqarib yuborish
    (`banChatMember`/`unbanChatMember`) uchun YETARLI EMAS, chunki bu metodlar
    kanalning RAQAMLI chat_id sini talab qiladi (masalan -1001234567890).

    Chat ID'ni olish: botni kanalga administrator etib qo'shib, kanalda istalgan
    xabarni botga forward qilish yoki @getidsbot kabi yordamchi bot orqali aniqlash
    mumkin.
    """

    channel_chat_id = models.BigIntegerField(
        null=True, blank=True,
        help_text="Yopiq kanalning raqamli chat ID'si (masalan -1001234567890). Bo'sh bo'lsa, avtomatik chiqarib yuborish ishlamaydi.",
    )
    auto_kick_on_expiry = models.BooleanField(
        default=True,
        help_text="Obuna muddati tugagan/bekor qilingan foydalanuvchi avtomatik ravishda kanaldan chiqarib yuborilsinmi",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kanal sozlamalari"
        verbose_name_plural = "Kanal sozlamalari"

    def __str__(self):
        return "Kanal sozlamalari"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj