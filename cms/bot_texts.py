# JOYLASHTIRISH MANZILI: ACADEMY_BACK/cms/bot_texts.py

"""
Botning "zavod sozlamasi" (factory default) xabar matnlari shu yerda, kod ichida
saqlanadi. Bu yerdagi lug'at endi ikkita vazifani bajaradi:

1. `cms.BotMessageTemplate` jadvali uchun boshlang'ich urug' (seed) manbai — har bir
   yozuv migratsiya orqali bazaga bir martalik ko'chiriladi va shu yerdan `default_text`
   sifatida saqlanadi ("Asliga qaytarish" tugmasi shu yerga qaytaradi).
2. Zaxira (fallback) manba — agar biror sababdan bazada/keshda yozuv topilmasa
   (masalan migratsiya hali ishlamagan yoki DB vaqtincha ishlamayapti), bot baribir
   shu statik matn bilan ishlashda davom etadi va yiqilib qolmaydi.

MUHIM: bu yerdagi slug'lar to'plami — botning ishlash tartibi (qaysi bosqichda qaysi
xabar chaqirilishi) hali ham TO'LIQ KOD orqali belgilanadi (handlerlar, celery
tasklar). Admin panel orqali faqat shu slug'larga mos MATN/SARLAVHA tahrirlanadi —
yangi slug qo'shish, slug o'chirish yoki chaqiruv tartibini o'zgartirish админ
panelidan MUMKIN EMAS. Shu bilan kontent va biznes-logika bir-biridan ajratilgan holda
qoladi.

Matn ichidagi {placeholder} lar bot service qatlamida (handlerlarda) `.replace(...)`
orqali to'ldiriladi — admin placeholder'ni matndan olib tashlasa yoki noma'lum
placeholder qo'shsa ham bot yiqilmaydi (shunchaki almashtirilmay qoladi).
"""

BOT_TEXTS = {
    # --- 1. Ro'yxatdan o'tish ---
    "ask_name": {
        "title": "Ismni so'rash",
        "text": "Ismingizni kiriting",
    },
    "ask_phone": {
        "title": "Telefon so'rash",
        "text": (
            "Telefon raqamingizni kiriting. Namuna: +998901234567 "
            "yoki pastdagi «Telefon raqamni yuborish» tugmasini bosing 👇"
        ),
    },
    "phone_accepted": {
        "title": "Telefon qabul qilindi",
        "text": "✅ Qabul qilindi.",
    },

    # --- 2. Taklif va to'lov ---
    "offer_intro": {
        "title": "Akademiya taklifi",
        "text": (
            "Davronbek Turdiev Akademiyasiga bir qadam qoldi.\n\n"
            "Davronbek Turdiev Akademiyasi – shaxsiy rivojlanishga yordam beradigan "
            "barcha bilimlar jamlangan yopiq jamiyat.\n\nAkademiyada sizni nimalar kutyapti?\n\n"
            "\"Super Intizom\" kursi - dangasalikdan qutilib, kuchli intizomni shakllantirishni o'rganasiz.\n\n"
            "Har oylik chellenjlar va vazifalar bo'ladi.\n\n"
            "Davronbek Turdiev tomonidan jonli efirda dars va savollarga javoblar\n\n"
            "Hech qayerga qo'yilmaydigan eksklyuziv foydali videolar\n\n"
            "Asosiy natija: kuchli intizom, tartibli hayot va doimiy rivojlanadigan insonlar muhiti"
        ),
    },
    "tariff_select": {
        "title": "Tarif tanlash",
        "text": (
            "To'lovni amalga oshirish qoldi.\n\nObuna narxi:\n\n{plan_lines}\n\n"
            "*To'lov qilingandan so'ng har 30 kun ichida obuna uchun to'lovi avtomatik tarzda "
            "yechiladi. To'lovni vaqtida qilmagan ishtirokchi kanaldan chiqarib yuboriladi. "
            "Bundan tashqari istalgan payt obunani bekor qilishingiz mumkin.\n\nObuna muddatini tanlang👇🏻"
        ),
    },
    "payment_method_select": {
        "title": "To'lov usulini tanlash",
        "text": (
            "To'lov usulini tanlang!\n\nTanlangan tarif: {plan_title}\n"
            "Narxi: {price_uzs} so'm (Chet el uchun - ${price_usd})\n\n"
            "*Istalgan payt obunani bekor qilishingiz mumkin.\n\n"
            "Quyidagi \"Uzcard/Humo\" yoki \"Chet eldan\" tugmalarini bosish orqali siz "
            "<a href=\"{offer_link}\">oferta</a> shartlariga rozilik berasiz"
        ),
    },

    # --- 3. Asosiy menyu va obuna holati ---
    "main_menu": {
        "title": "Asosiy menyu",
        "text": "Davronbek Turdiev Akademiyasi ishtirokchisining menyusi",
    },
    "subscription_status": {
        "title": "Obuna holati",
        "text": (
            "Davronbek Turdiev Akademiyaga obuna holati:\n\n{status}\n\n"
            "Keyingi to'lov sanasi: {next_date}\nAvtomatik to'lov: {autopay}\nKarta: {masked_pan}"
        ),
    },
    "card_change_intro": {
        "title": "Karta almashtirish",
        "text": (
            "💳 Karta almashtirish\n\nSizning joriy obunangiz:\n• Tarif: {plan_title}\n"
            "• Narxi: {price} so'm\n• Keyingi to'lov sanasi: {next_date}\n\n"
            "🔄 Siz faqat keyingi avtomatik to'lov uchun yangi kartani bog'laysiz.\n\n"
            "✅ Hozir kartangizdan hech qanday mablag' yechilmaydi.\n\n"
            "💳 To'lov faqat {next_date} sanasida, obunangizni davom ettirish vaqti kelganda "
            "yangi kartadan avtomatik yechiladi.\n\n"
            "⚠️ To'lov muvaffaqiyatli saqlangandan so'ng yangi karta asosiy karta sifatida "
            "belgilanadi va keyingi avtomatik to'lovlar aynan shu kartadan amalga oshiriladi.\n\n"
            "\"Davom etish\" tugmasini bosish orqali siz karta ma'lumotlarini yangilash "
            "jarayonini boshlaysiz."
        ),
    },

    # --- 4. Avto-to'lov — eslatmalar ---
    "renewal_reminder_3d": {
        "title": "Eslatma — 3 kun qoldi",
        "text": (
            "⏰ Obunangiz tugashiga 3 kun qoldi\nTarif: {tarif_name}\nObuna tugash sanasi: {expires_at}\n\n"
            "Belgilangan kuni oylik obuna to'lovi avtomatik yechiladi.\n\n"
            "Akademiyadan chiqib ketsangiz, faqat akademiya a'zolari uchun hech qayerda qo'yilmaydigan "
            "eksklyuziv videolarni ko'rish va umumiy chat guruhiga kirish imkoniyatini yo'qotasiz.\n\n"
            "Akademiyadan chiqib ketmaslik uchun kartangizda yetarli mablag' borligini tekshiring."
        ),
    },
    "renewal_reminder_2d": {
        "title": "Eslatma — 2 kun qoldi",
        "text": (
            "⏰ Obunangiz tugashiga 2 kun qoldi\n\nTarif: {tarif_name}\nObuna tugash sanasi: {expires_at}\n\n"
            "Belgilangan kuni oylik obuna to'lovi avtomatik yechiladi.\n\n"
            "⚠️ Eslatma: To'lovni vaqtida amalga oshirmasangiz, Akademiya va umumiy chat guruhidan "
            "chiqarilasiz hamda \"Super Intizom\" kursi darslarini ko'ra olmaysiz va jonli efirlarda "
            "qatnashish imkoniyatini yo'qotasiz.\n"
            "Akademiyadagi barcha imkoniyatlarni saqlab qolish uchun kartangizda yetarli mablag' "
            "borligini tekshiring."
        ),
    },
    "renewal_reminder_1d": {
        "title": "Eslatma — 1 kun qoldi",
        "text": (
            "⏰ Obunangiz tugashiga 1 kun qoldi\nTarif: {tarif_name}\nObuna tugash sanasi: {expires_at}\n\n"
            "Belgilangan kuni oylik obuna to'lovi avtomatik yechiladi.\n\n"
            "⚠️ Eslatma: Akademiyadan chiqib ketsangiz, akademiyadagi hozirgi darajangizdan "
            "\"boshlovchi\" darajasiga tushirilasiz va keyingi oy uchun sirli sovg'alarni qo'lga "
            "kiritish imkoniyatini yo'qotasiz.\n\n"
            "Akademiyaga esa keyingi qabul ochilganida qo'shilishingiz mumkin. Keyingi qabul sanasi "
            "qachon bo'lishi noma'lum"
        ),
    },
    "renewal_reminder_1d_sms": {
        "title": "SMS eslatma — 1 kun qoldi",
        "text": (
            "Yaxshimisiz? Davronbek Turdiev Akademiyasi uchun oylik obunangiz ertaga tugaydi. "
            "Obunani uzaytirishda muammo bo'lmasligi uchun kartangiz balansini tekshiring"
        ),
    },

    # --- 5. Avto-to'lov — muvaffaqiyatsiz urinishlar ---
    "renewal_processing_alert": {
        "title": "Ishlanmoqda (alert)",
        "text": "🔄 Obuna to'lovini yechish amalga oshirilmoqda...",
    },
    "renewal_fail_1": {
        "title": "To'lov yechilmadi — 1-urinish",
        "text": (
            "⚠️ Keyingi oy uchun to'lovingiz amalga oshmadi\n\n"
            "Obunangiz to'xtab qolmasligi uchun karta balansingizni tekshirishingizni so'raymiz.\n"
            "📌 Tarif: {tarif_name}\n💰 Narxi: {amount} so'm\n❌ Sababi: {error_reason}\n"
            "🔄 Tez orada to'lovni qayta yechishga urinib ko'ramiz.\n\n"
            "To'lovni hozirning o'zida qaytadan amalga oshirish uchun quyidagi \"Davom etish\" tugmasini bosing."
        ),
    },
    "renewal_fail_2": {
        "title": "To'lov yechilmadi — 2-urinish",
        "text": (
            "⚠️ Keyingi oy uchun obuna to'lovingiz amalga oshirilmadi!\n\n"
            "Obunangiz to'xtab qolmasligi uchun karta balansingizni obuna uchun yetarli {amount} so'mga "
            "to'ldiring va to'lovni qaytadan amalga oshirish uchun quyidagi \"Davom etish\" tugmasini bosing.\n"
            "📌 Tarif: {tarif_name}\n💰 Narxi: {amount} so'm\n❌ Sababi: {error_reason}\n"
            "⏰ 48 soat ichida to'lov amalga oshirilmasa, akademiyadan chiqarib yuborilasiz!"
        ),
    },
    "renewal_fail_3": {
        "title": "To'lov yechilmadi — 3-urinish",
        "text": (
            "⚠️ Keyingi oy uchun obuna to'lovingiz amalga oshirilmadi!\n\n"
            "Akademiyadagi foydali darslar, audiopodkastlar va eksklyuziv kontentlardan foydalanishni "
            "davom ettirish uchun kartangiz balansini yetarli {amount} so'mga to'ldiring.\n"
            "📌 Tarif: {tarif_name}\n💰 Narxi: {amount} so'm\n❌ Sababi: {error_reason}\n"
            "⏰ 24 soat ichida to'lov amalga oshirilmasa, akademiyadan chiqarib yuborilasiz!"
        ),
    },
    "renewal_fail_4": {
        "title": "To'lov yechilmadi — 4-urinish",
        "text": (
            "⚠️ Keyingi oy uchun obuna to'lovingiz amalga oshirilmadi!\n\n"
            "Obunangiz to'xtab qolmasligi uchun karta balansingizni obuna uchun yetarli {amount} so'mga "
            "to'ldiring va to'lovni qaytadan amalga oshirish uchun quyidagi \"Davom etish\" tugmasini bosing.\n"
            "📌 Tarif: {tarif_name}\n💰 Narxi: {amount} so'm\n❌ Sababi: {error_reason}\n"
            "⏰ 6 soat ichida to'lov amalga oshirilmasa, akademiyadan chiqarib yuborilasiz!"
        ),
    },
    "renewal_card_expired": {
        "title": "Karta muddati o'tgan",
        "text": (
            "⚠️ Keyingi oy uchun to'lovingiz amalga oshmadi\n\n"
            "Kiritilgan kartangizning amal qilish muddati tugaganligi sababli, akademiya oylik "
            "to'lovi amalga oshirilmadi.\n\n"
            "To'lovni amalga oshirish uchun pastdagi \"Kartani almashtirish\" tugmasi orqali "
            "kartangizni almashtiring."
        ),
    },
    "renewal_card_change_intro": {
        "title": "Karta almashtirish (kaskad ichida)",
        "text": (
            "Obuna to'lov uchun plastik kartani almashtirish 👇\n\n"
            "📌 Sizning tarifingiz: {tarif_name}\n💰 Narxi: {amount} so'm\n\n"
            "Karta ma'lumotlarini yangilash uchun \"Davom etish\" tugmasini bosing.\n\n"
            "\"Davom etish\" tugmasini bosish orqali oferta shartlariga rozilik bildirasiz."
        ),
    },
    "renewal_success": {
        "title": "To'lov muvaffaqiyatli",
        "text": (
            "✅ Tabriklaymiz!\n\nKeyingi oy uchun obuna to'lovingiz muvaffaqiyatli qabul qilindi!\n"
            "📌 Tarif: {tarif_name}\n💰 Narxi: {amount} so'm\n📅 Obunangiz tugash muddati: {expires_at}"
        ),
    },
    "renewal_cancelled": {
        "title": "Obuna to'xtatildi",
        "text": (
            "🚫 Obunangiz to'xtatildi!\n\n"
            "Keyingi oy uchun to'lovni o'z vaqtida amalga oshirmaganligingiz sababli Davronbek Turdiev "
            "Akademiyasi kanali va chat guruhidan chiqarildingiz.\n\n"
            "Akademiyadagi barcha imkoniyatlar – har oy beriladigan maxsus sovg'alar, Super intizom "
            "kursi, hech qayerda qo'yilmaydigan eksklyuziv videolarni ko'rish, challenge'larda "
            "qatnashish imkoniyatini yo'qotdingiz.\n\n"
            "Akademiyaga qayta obuna bo'lish uchun pastdagi \"Obuna tiklash\" tugmasini bosing"
        ),
    },

    # --- 6. Qabul yopiq ---
    "admission_closed": {
        "title": "Qabul yopiq",
        "text": (
            "Hozirda Davronbek Turdiev Akademiyasiga yangi qabul yopiq.\n\n"
            "Keyingi qabul boshlanganda xabardor qilamiz. Kuzatib boring!"
        ),
    },
}


# Admin panelidagi konstruktor canvasida xabarlarni guruhlab ko'rsatish uchun.
# Guruh — faqat vizual tashkillashtirish, botning chaqiruv tartibiga hech qanday
# ta'sir qilmaydi (u hamon kod ichida, handlerlar/tasklar tartibida belgilangan).
BOT_MESSAGE_GROUPS = {
    # --- 1. Ro'yxatdan o'tish ---
    "ask_name": "onboarding",
    "ask_phone": "onboarding",
    "phone_accepted": "onboarding",
    # --- 2. Taklif va to'lov ---
    "offer_intro": "payment",
    "tariff_select": "payment",
    "payment_method_select": "payment",
    # --- 3. Asosiy menyu va obuna holati ---
    "main_menu": "main_menu",
    "subscription_status": "main_menu",
    "card_change_intro": "main_menu",
    # --- 4. Avto-to'lov — eslatmalar ---
    "renewal_reminder_3d": "renewal_reminders",
    "renewal_reminder_2d": "renewal_reminders",
    "renewal_reminder_1d": "renewal_reminders",
    "renewal_reminder_1d_sms": "renewal_reminders",
    # --- 5. Avto-to'lov — muvaffaqiyatsiz urinishlar ---
    "renewal_processing_alert": "renewal_fail_cascade",
    "renewal_fail_1": "renewal_fail_cascade",
    "renewal_fail_2": "renewal_fail_cascade",
    "renewal_fail_3": "renewal_fail_cascade",
    "renewal_fail_4": "renewal_fail_cascade",
    "renewal_card_expired": "renewal_fail_cascade",
    "renewal_card_change_intro": "renewal_fail_cascade",
    "renewal_success": "renewal_fail_cascade",
    "renewal_cancelled": "renewal_fail_cascade",
    # --- 6. Qabul yopiq ---
    "admission_closed": "admission",
}

# Huquqiy/nozik matn (oferta havolasi yoki rozilik so'zlari) bor slug'lar — bular
# uchun `BotMessageTemplate.is_locked` boshlang'ich holatda `True` qilib urug'lanadi
# (faqat superuser tahrirlay oladi). Migratsiyadan keyin admin panelning o'zidan
# istalgan vaqt yoqilishi/o'chirilishi mumkin.
DEFAULT_LOCKED_SLUGS = {"payment_method_select", "renewal_card_change_intro"}


def get_bot_text(slug: str, default: str = "") -> str:
    """
    Slug bo'yicha joriy (admin panelda tahrirlangan bo'lishi mumkin) matnni qaytaradi.

    Manba tartibi: Redis kesh -> baza (`BotMessageTemplate`) -> shu fayldagi statik
    `BOT_TEXTS` (zaxira). Bu funksiya hamon sinxron va tez (kesh hit bo'lsa I/O yo'q),
    shuning uchun async handlerlar ichida ilgarigidek to'g'ridan-to'g'ri chaqirilaveradi.
    """
    row = _get_cached_row(slug)
    if row and row.get("text"):
        return row["text"]
    entry = BOT_TEXTS.get(slug)
    return entry["text"] if entry else default


def get_bot_title(slug: str, default: str = "") -> str:
    row = _get_cached_row(slug)
    if row and row.get("title"):
        return row["title"]
    entry = BOT_TEXTS.get(slug)
    return entry["title"] if entry else default


_CACHE_KEY = "cms:bot_message_templates:v1"
_CACHE_TTL_SECONDS = 300  # xavfsizlik uchun TTL — signal orqali invalidatsiya asosiy yo'l


def _get_cached_row(slug: str) -> dict | None:
    rows = _load_cache()
    return rows.get(slug)


def _load_cache() -> dict:
    """
    Barcha `BotMessageTemplate` qatorlarini Redis keshiga (yoki kesh hit bo'lsa —
    shundan) yuklaydi.

    MUHIM: bu funksiya ham sinxron kontekstdan (celery tasklar, Django admin),
    ham aiogram'ning ASYNC handlerlaridan (masalan `get_bot_text` orqali,
    `cms.services.asend_static` ichida) to'g'ridan-to'g'ri chaqiriladi. Kesh
    "hit" bo'lsa muammo yo'q (DB'ga umuman tushilmaydi). Lekin kesh "miss"
    bo'lganda (masalan bot process yangi ishga tushgan, yoki TTL — 5 daqiqa —
    tugagan bo'lsa) pastdagi DB so'rovi ALOHIDA thread'da bajariladi — aks
    holda async handler ichida to'g'ridan-to'g'ri DB so'rov yuborish Django'ning
    `SynchronousOnlyOperation` xatosini beradi (aiogram polling async ishlagani
    uchun). Alohida thread bu tekshiruvni xavfsiz chetlab o'tadi, chunki
    tekshiruv "joriy thread'da asyncio event loop ishlayaptimi" deb qaraydi —
    yangi oddiy thread'da esa yo'q.
    """
    from django.core.cache import cache

    try:
        rows = cache.get(_CACHE_KEY)
    except Exception as exc:  # noqa: BLE001 — kesh (Redis) vaqtincha ishlamasa ham bot/admin panel yiqilmasin
        import logging

        logging.getLogger(__name__).warning(
            "Bot matnlari keshini o'qib bo'lmadi (%s) — to'g'ridan-to'g'ri bazadan o'qiladi.", exc,
        )
        rows = None
    if rows is not None:
        return rows

    rows = _fetch_rows_from_db_in_thread()
    try:
        cache.set(_CACHE_KEY, rows, _CACHE_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 — yozib bo'lmasa ham funksiya baribir to'g'ri natija qaytaradi
        import logging

        logging.getLogger(__name__).warning(
            "Bot matnlari keshiga yozib bo'lmadi (%s) — keshsiz davom etiladi.", exc,
        )
    return rows


def _fetch_rows_from_db_in_thread() -> dict:
    import threading

    from .models import BotMessageTemplate

    result: dict = {}
    errors: list = []

    def _run():
        from django.db import connection
        try:
            result.update({
                row["slug"]: row
                for row in BotMessageTemplate.objects.values("slug", "title", "text")
            })
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()  # bu thread'ga tegishli DB ulanishini darhol yopamiz

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result


def invalidate_bot_text_cache() -> None:
    """`BotMessageTemplate` saqlanganda/o'chirilganda chaqiriladi (signal orqali).

    MUHIM: kesh (Redis) vaqtincha ishlamasa ham (masalan lokal dev muhitda Redis
    ishga tushirilmagan bo'lsa), bu funksiya XATOLIK BILAN YIQILMASLIGI kerak —
    aks holda allaqachon bazaga MUVAFFAQIYATLI saqlangan yozuv (masalan yangi
    bot xabari yoki avto-to'lov bosqichi) faqat kesh tozalanmagani sabab 500
    xatosi bilan qaytadi (admin panelda "xabar qo'sholmayapman" ko'rinishida).
    Kesh tozalanmasa ham, `_CACHE_TTL_SECONDS` (5 daqiqa) orqali o'zi eskiradi.
    """
    from django.core.cache import cache

    try:
        cache.delete(_CACHE_KEY)
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(
            "Bot matnlari keshini tozalab bo'lmadi (%s) — TTL orqali o'zi eskiradi.", exc,
        )


# Admin paneldagi "media biriktirish" dropdown'i uchun (BotMedia.slug choices)
BOT_MESSAGE_CHOICES = [(slug, entry["title"]) for slug, entry in BOT_TEXTS.items()]