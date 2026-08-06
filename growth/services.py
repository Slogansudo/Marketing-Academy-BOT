# JOYLASHTIRISH MANZILI: ACADEMY_BACK/growth/services.py

"""
Qabul (admission) va reklama kampaniyalari (referal havolalar) uchun yordamchi
funksiyalar. `bot/handlers/registration.py` (async, aiogram) va
`subscriptions/services/subscription_service.py` (sync, webhook) ikkalasi ham
shu modulga tayanadi.
"""

from django.db.models import F

from .models import AdmissionSettings, ReferralLink


async def aresolve_referral_link(code: str | None) -> ReferralLink | None:
    """
    `/start <code>` argumentiga mos FAOL referal havolani topadi. Havola mavjud
    bo'lmasa yoki `is_active=False` bo'lsa (masalan kampaniya to'xtatilgan),
    None qaytaradi — bu holatda foydalanuvchi oddiy (referalsiz) kirgan deb
    hisoblanadi.
    """
    if not code:
        return None
    return await ReferralLink.objects.filter(code=code, is_active=True).afirst()


async def aregister_lead(referral_link: ReferralLink | None) -> None:
    """
    Referal havola orqali kirgan YANGI foydalanuvchi uchun `leads_count` +1.
    Faqat foydalanuvchi ENDI birinchi marta yaratilganda chaqiriladi
    (`registration.py`dagi `created=True` tekshiruvi orqali) — shu sabab bu
    yerda qayta tekshirish shart emas, lekin xavfsizlik uchun None holatini
    baribir e'tiborsiz qoldiramiz.
    """
    if not referral_link:
        return
    await ReferralLink.objects.filter(pk=referral_link.pk).aupdate(leads_count=F("leads_count") + 1)


def register_sale(referral_link: ReferralLink | None) -> None:
    """
    Referal havola orqali kirgan foydalanuvchining BIRINCHI (ongli) to'lovi
    uchun `sales_count` +1. Sync — `subscription_service.py`dagi
    `activate_or_renew_subscription` (webhook, @transaction.atomic) ichidan
    chaqiriladi, shu sababli aiogram/async emas.
    """
    if not referral_link:
        return
    ReferralLink.objects.filter(pk=referral_link.pk).update(sales_count=F("sales_count") + 1)


async def ais_admission_open(referral_link: ReferralLink | None) -> bool:
    """
    HALI RO'YXATDAN O'TMAGAN foydalanuvchi uchun ro'yxatdan o'tish oqimini
    boshlash mumkinmi:

    - `AdmissionSettings.is_open=True` bo'lsa — hammaga ochiq.
    - `is_open=False` bo'lsa-da, `allow_referral_when_closed=True` VA
      foydalanuvchi FAOL referal havola orqali kirgan bo'lsa — baribir ochiq
      (maqsadli reklama kampaniyasi uchun).
    - Aks holda — yopiq (`admission_closed` xabari ko'rsatiladi).

    Allaqachon ro'yxatdan o'tgan/obunasi bor ishtirokchilarga bu funksiya
    UMUMAN chaqirilmaydi (`registration.py`da faqat yangi foydalanuvchi
    oqimida ishlatiladi).
    """
    settings_obj = await AdmissionSettings.aload()
    if settings_obj.is_open:
        return True
    return bool(settings_obj.allow_referral_when_closed and referral_link and referral_link.is_active)
