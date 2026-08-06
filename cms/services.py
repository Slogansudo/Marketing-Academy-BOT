# JOYLASHTIRISH MANZILI: ACADEMY_BACK/cms/services.py

"""
Bot xabarlarini yuborish uchun umumiy yordamchi funksiyalar.

Matn har doim `bot_texts.BOT_TEXTS` dan (statik, bazasiz) olinadi. Agar admin panel orqali
shu slug'ga media biriktirilgan bo'lsa, xabar media turi (video/audio/rasm) bilan mos keladigan
Telegram metodi orqali (caption'da matn bilan) yuboriladi, aks holda oddiy matn ko'rinishida —
shu bilan istalgan statik xabarga istalgan turdagi media biriktirish imkoniyati umumiy tarzda
ta'minlanadi.

DUMALOQ VIDEO (video note): Telegramning sendVideoNote metodi caption'ni qo'llab-quvvatlamaydi,
shuning uchun bu holatda video note alohida, matn esa undan keyin ALOHIDA xabar sifatida yuboriladi.

FILE_ID KESHLASH: katta (30-40 MB+) fayl har safar qayta yuklansa, yuborish sezilarli
sekinlashadi. Shu sababli birinchi muvaffaqiyatli yuborishdan keyin Telegram qaytargan
`file_id` avtomatik ravishda `BotMedia.telegram_file_id`ga saqlanadi — keyingi barcha
yuborishlar shu ID orqali, qayta yuklamasdan, deyarli bir zumda amalga oshadi.
"""

import json

import requests
from aiogram.types import FSInputFile
from asgiref.sync import sync_to_async
from django.conf import settings

from .bot_texts import get_bot_text
from .models import BotMedia

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# Media turi (+ video shakli) -> Telegram metodi va multipart/form-data maydon nomi.
# `send_raw_with_media` va `renewal_notifier.py` ikkalasi ham shu xaritadan foydalanadi,
# shuning uchun ikki joyda alohida-alohida saqlanib, bir-biridan chetga chiqib qolmaydi.
MEDIA_METHOD = {
    ("video", "circle"): ("sendVideoNote", "video_note"),
    ("video", "rectangle"): ("sendVideo", "video"),
    ("audio", "rectangle"): ("sendAudio", "audio"),
    ("photo", "rectangle"): ("sendPhoto", "photo"),
}


async def aget_bot_media(slug: str) -> BotMedia | None:
    return await BotMedia.objects.filter(slug=slug).afirst()


def get_bot_media(slug: str) -> BotMedia | None:
    return BotMedia.objects.filter(slug=slug).first()


def resolve_media_source(media: BotMedia):
    """
    aiogram uchun yuborish manbasini tanlaydi: keshlangan file_id (satr) -> lokal fayl
    (`FSInputFile` — aiogramga to'g'ri yuklash uchun, oddiy path satri EMAS) -> tashqi url.
    file_id mavjud bo'lsa, fayl umuman qayta o'qilmaydi/yuklanmaydi.
    """
    if not media:
        return None
    if media.telegram_file_id:
        return media.telegram_file_id
    if media.file:
        return FSInputFile(media.file.path)
    if media.video_url:
        return media.video_url
    return None


def resolve_media_payload_source(media: BotMedia):
    """
    Xom (aiogramsiz, `requests` bilan) Telegram HTTP API chaqiruvlari uchun.
    `(value, is_file)` qaytaradi: `is_file=True` bo'lsa `value` — ochish mumkin bo'lgan
    Django `FieldFile` (multipart yuklash uchun), aks holda `value` — file_id yoki url satri.
    """
    if not media:
        return None, False
    if media.telegram_file_id:
        return media.telegram_file_id, False
    if media.file:
        return media.file, True
    if media.video_url:
        return media.video_url, False
    return None, False


async def _acache_file_id(media: BotMedia, file_id: str | None) -> None:
    """Yuborilgan media javobidagi file_id'ni birinchi martagina saqlaydi."""
    if not media or media.telegram_file_id or not file_id:
        return
    media.telegram_file_id = file_id
    await media.asave(update_fields=["telegram_file_id"])


def cache_file_id_from_result(media: BotMedia, result: dict | None) -> None:
    """Xom Telegram API javobi (`{"result": {...}}`) dan media turiga mos file_id'ni keshlaydi."""
    if not media or media.telegram_file_id or not result:
        return
    payload = (result or {}).get("result") or {}
    file_id = None
    if "video_note" in payload:
        file_id = (payload.get("video_note") or {}).get("file_id")
    elif "video" in payload:
        file_id = (payload.get("video") or {}).get("file_id")
    elif "audio" in payload:
        file_id = (payload.get("audio") or {}).get("file_id")
    elif payload.get("photo"):
        file_id = payload["photo"][-1].get("file_id")
    if file_id:
        media.telegram_file_id = file_id
        media.save(update_fields=["telegram_file_id"])


async def asend_static(send_target, slug: str, text: str | None = None, reply_markup=None, **extra):
    """
    `send_target` — `.answer()`, `.answer_video()`, `.answer_photo()`, `.answer_audio()` va
    `.answer_video_note()` metodlariga ega aiogram obyekti (masalan `Message`). Yangi xabar
    sifatida yuboradi (edit emas).

    `text` berilmasa, statik matn (`slug` bo'yicha) ishlatiladi — chaqiruvchi tomon
    placeholder'larni oldindan almashtirib berishi mumkin.
    """
    if text is None:
        text = get_bot_text(slug)

    media = await aget_bot_media(slug)
    source = resolve_media_source(media)
    if not source:
        return await send_target.answer(text, reply_markup=reply_markup, **extra)

    if media.is_circle_video:
        # sendVideoNote caption'ni qo'llab-quvvatlamaydi — matn alohida xabar sifatida ketadi.
        result = await send_target.answer_video_note(video_note=source)
        await _acache_file_id(media, result.video_note.file_id if result.video_note else None)
        return await send_target.answer(text, reply_markup=reply_markup, **extra)

    if media.media_type == BotMedia.MediaType.PHOTO:
        result = await send_target.answer_photo(photo=source, caption=text, reply_markup=reply_markup, **extra)
        await _acache_file_id(media, result.photo[-1].file_id if result.photo else None)
        return result

    if media.media_type == BotMedia.MediaType.AUDIO:
        result = await send_target.answer_audio(audio=source, caption=text, reply_markup=reply_markup, **extra)
        await _acache_file_id(media, result.audio.file_id if result.audio else None)
        return result

    result = await send_target.answer_video(video=source, caption=text, reply_markup=reply_markup, **extra)
    await _acache_file_id(media, result.video.file_id if result.video else None)
    return result


def render_text(text: str, context: dict | None = None) -> str:
    """
    Matn ichidagi `{placeholder}` larni `context` lug'atidagi qiymatlar bilan almashtiradi.
    `context`da bo'lmagan placeholder o'zgarishsiz qoladi (bot yiqilmaydi, shunchaki
    xom `{nomi}` ko'rinishida qolib ketadi — admin panelda ham shu xulq-atvor ko'rsatiladi).
    """
    text = text or ""
    for key, value in (context or {}).items():
        text = text.replace("{" + str(key) + "}", str(value))
    return text


def _ordered_group_steps(group: str, **filters) -> list:
    """Berilgan guruh (kategoriya) uchun FAOL qatorlarni pozitsiya bo'yicha tartiblab qaytaradi.
    `**filters` — masalan `trigger_event=...`, `attempt_number=...` (kaskad guruhi uchun).

    DIQQAT: bu funksiya SINXRON — Django ORM'ga to'g'ridan-to'g'ri murojaat qiladi.
    Async (aiogram) kontekstidan chaqirilganda albatta `_aordered_group_steps` (pastda)
    orqali, `sync_to_async` bilan o'ralgan holda chaqirilishi SHART — aks holda
    `SynchronousOnlyOperation` xatosi chiqadi. Sinxron joylarda (celery task'lar,
    `send_group_step_raw`, `send_cascade_stage_raw`) shu funksiya to'g'ridan-to'g'ri
    ishlatilaveradi.
    """
    from .models import BotMessageTemplate

    qs = BotMessageTemplate.objects.filter(group=group, is_active=True, **filters)
    return list(qs.order_by("position", "id"))


# `_ordered_group_steps`ning async-kontekst uchun xavfsiz o'ramasi. `thread_sensitive=True`
# — Django ORM connection'lari thread-local bo'lgani uchun har doim BITTA (asosiy) thread'da
# ishlashini kafolatlaydi; aks holda vaqti-vaqti bilan "connection already closed" kabi
# boshqa xatolar chiqishi mumkin.
_aordered_group_steps = sync_to_async(_ordered_group_steps, thread_sensitive=True)


def _trailing_custom_steps(steps: list, from_index: int) -> list:
    """`steps[from_index]`dan KEYIN, keyingi CORE qadamgacha joylashgan CUSTOM
    qatorlarni qaytaradi — bular "shu CORE qadamdan keyin ergashadigan qo'shimcha
    xabarlar" (admin konstruktorda ikkita CORE karta orasiga qo'shgan bo'lishi mumkin)."""
    from .models import BotMessageTemplate

    trailing = []
    for step in steps[from_index + 1:]:
        if step.step_type != BotMessageTemplate.StepType.CUSTOM:
            break
        trailing.append(step)
    return trailing


async def asend_group_step(send_target, group: str, slug: str, context: dict | None = None, reply_markup=None, **extra):
    """
    Dinamik voronka: interaktiv CORE bosqich (masalan 'ask_phone', 'offer_intro')
    `asend_static(target, slug, ...)` o'rniga shu funksiya orqali yuboriladi.

    Avval CORE qadamning o'zi yuboriladi (reply_markup shu yerga tegishli — bosqich
    kutayotgan tugma/klaviatura), so'ng — agar admin konstruktorda shu qadamdan KEYIN,
    keyingi CORE qadamgacha bo'lgan oraliqqa CUSTOM xabar(lar) qo'shgan bo'lsa —
    ular ham avtomatik ravishda, oddiy matn/media xabari sifatida, ketma-ket yuboriladi.

    Bazadan mos CORE qator topilmasa (masalan migratsiya hali ishlamagan yoki kesh
    muammosi) — zaxira sifatida to'g'ridan-to'g'ri statik `asend_static` ishlatiladi,
    oraliq CUSTOM xabarlarsiz (chunki qaysi guruh ichida ekanini aniqlab bo'lmaydi).
    """
    context = context or {}
    steps = await _aordered_group_steps(group)
    index = next((i for i, s in enumerate(steps) if s.slug == slug), None)

    if index is None:
        return await asend_static(send_target, slug, reply_markup=reply_markup, **extra)

    result = await asend_static(
        send_target, slug, text=render_text(steps[index].text, context), reply_markup=reply_markup, **extra,
    )
    for step in _trailing_custom_steps(steps, index):
        await asend_static(send_target, step.slug, text=render_text(step.text, context))
    return result


async def asend_trailing_customs(send_target, group: str, slug: str, context: dict | None = None) -> None:
    """
    `asend_group_step`ning "faqat ergashuvchi CUSTOM xabarlarni yuborish" varianti —
    CORE qadamning o'zi allaqachon BOSHQA usulda (masalan `callback.message.edit_text`)
    ekranga chiqarilgan holatlar uchun (masalan asosiy menyu, obuna holati, karta
    almashtirish — bular mavjud xabarni TAHRIRLAYDI, yangi xabar yubormaydi). CORE
    qadamning o'zini QAYTA yubormaydi — faqat undan keyingi CUSTOM qatorlarni.
    """
    context = context or {}
    steps = await _aordered_group_steps(group)
    index = next((i for i, s in enumerate(steps) if s.slug == slug), None)
    if index is None:
        return
    for step in _trailing_custom_steps(steps, index):
        await asend_static(send_target, step.slug, text=render_text(step.text, context))


async def asend_cascade_stage(send_target, trigger_event: str, attempt_number: int | None = None,
                               context: dict | None = None, reply_markup=None, **extra):
    """
    Avto-to'lov kaskadi (`renewal_fail_cascade`) uchun — berilgan hodisa (va agar
    `trigger_event='attempt'` bo'lsa, aniq urinish raqami) uchun admin konstruktorda
    FAOL qilib qo'yilgan BARCHA xabarlarni (CORE + CUSTOM, pozitsiya bo'yicha) ketma-ket
    yuboradi. Tugma (`reply_markup`) faqat OXIRGI xabarga biriktiriladi. Agar admin shu
    hodisaga/urinishga hech qanday xabar qo'ymagan bo'lsa — hech narsa yuborilmaydi
    (bu xato emas — masalan 2-urinishni ataylab "jim" qoldirish tizim tomonidan
    qo'llab-quvvatlanadi). Interaktiv (aiogram) kontekstlar uchun — masalan
    'Kartani almashtirish' bosilganda kaskad ichida ko'rsatiladigan ekran.
    """
    from .models import BotMessageTemplate

    filters = {"trigger_event": trigger_event}
    if trigger_event == "attempt":
        filters["attempt_number"] = attempt_number
    steps = await _aordered_group_steps(BotMessageTemplate.CASCADE_GROUP, **filters)
    if not steps:
        return None

    context = context or {}
    last_index = len(steps) - 1
    result = None
    for index, step in enumerate(steps):
        result = await asend_static(
            send_target, step.slug, text=render_text(step.text, context),
            reply_markup=reply_markup if index == last_index else None, **extra,
        )
    return result


def send_group_step_raw(group: str, slug: str, telegram_id: int, context: dict | None = None,
                         reply_markup: dict | None = None) -> None:
    """`asend_group_step`ning sinxron/xom (celery task, aiogram kontekstisiz) ekvivalenti."""
    context = context or {}
    steps = _ordered_group_steps(group)
    index = next((i for i, s in enumerate(steps) if s.slug == slug), None)

    if index is None:
        send_raw_with_media(slug, telegram_id, render_text(get_bot_text(slug), context), reply_markup=reply_markup)
        return

    send_raw_with_media(slug, telegram_id, render_text(steps[index].text, context), reply_markup=reply_markup)
    for step in _trailing_custom_steps(steps, index):
        send_raw_with_media(step.slug, telegram_id, render_text(step.text, context))


def send_cascade_stage_raw(telegram_id: int, trigger_event: str, attempt_number: int | None = None,
                            context: dict | None = None, reply_markup: dict | None = None) -> bool:
    """`asend_cascade_stage`ning sinxron/xom (celery task) ekvivalenti. Kamida bitta
    xabar yuborilgan bo'lsa `True`, admin bu hodisaga/urinishga hech narsa
    qo'ymagan bo'lsa (masalan tashlab ketilgan urinish) `False` qaytaradi."""
    from .models import BotMessageTemplate

    filters = {"trigger_event": trigger_event}
    if trigger_event == "attempt":
        filters["attempt_number"] = attempt_number
    steps = _ordered_group_steps(BotMessageTemplate.CASCADE_GROUP, **filters)
    if not steps:
        return False

    context = context or {}
    last_index = len(steps) - 1
    for index, step in enumerate(steps):
        send_raw_with_media(
            step.slug, telegram_id, render_text(step.text, context),
            reply_markup=reply_markup if index == last_index else None,
        )
    return True


def send_raw_with_media(slug: str, telegram_id: int, text: str, reply_markup: dict | None = None) -> None:
    """
    `asend_static`ning sinxron/xom (aiogramsiz) ekvivalenti — Telegramning HTTP API'siga
    to'g'ridan-to'g'ri `requests` orqali murojaat qiladi. Aiogram konteksti mavjud bo'lmagan
    joylarda (masalan Celery task'lari yoki admin panelning "sinov xabari" funksiyasi) shu slug
    uchun biriktirilgan `BotMedia` bo'lsa uni ham (rasm/video/audio, caption sifatida `text`
    bilan) yuboradi, bo'lmasa oddiy matn xabari yuboradi.

    Dumaloq video (video note) caption qabul qilmaydi — bu holatda matn video notedan keyin
    ALOHIDA xabar sifatida yuboriladi (`asend_static`dagi kabi).
    """
    media = get_bot_media(slug)
    value, is_file = resolve_media_payload_source(media)

    def _send_text_only():
        url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendMessage")
        payload = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

    if not value:
        _send_text_only()
        return

    shape = "circle" if media.is_circle_video else "rectangle"
    method, field = MEDIA_METHOD[(media.media_type, shape)]
    is_video_note = field == "video_note"

    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    data = {"chat_id": telegram_id}
    if not is_video_note:
        data["caption"] = text
        data["parse_mode"] = "HTML"
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

    if is_file:
        with value.open("rb") as f:
            response = requests.post(url, data=data, files={field: f}, timeout=60)
    else:
        data[field] = value
        response = requests.post(url, data=data, timeout=15)

    response.raise_for_status()
    cache_file_id_from_result(media, response.json())

    if is_video_note:
        _send_text_only()