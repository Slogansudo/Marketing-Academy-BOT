import json

import requests
from celery import shared_task
from django.conf import settings

from users.models import TelegramUser

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _send_message(telegram_id: int, text: str, reply_markup: dict | None = None):
    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendMessage")
    payload = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()


def _send_photo(telegram_id: int, photo_source, caption: str, reply_markup: dict | None = None) -> str | None:
    """
    Rasmni yuboradi va Telegram qaytargan `file_id`ni natija sifatida beradi.

    `photo_source` ikki xil bo'lishi mumkin:
    - `str` — avval keshlangan Telegram file_id (bu holda fayl umuman diskdan
      o'qilmaydi/yuklanmaydi, yuborish deyarli bir zumda amalga oshadi);
    - Django `FieldFile` (masalan `broadcast.image`) — hali file_id keshlanmagan
      bo'lsa, fayl diskdan multipart/form-data orqali yuklanadi.
    """
    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendPhoto")
    data = {"chat_id": telegram_id, "caption": caption, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if isinstance(photo_source, str):
        data["photo"] = photo_source
        response = requests.post(url, data=data, timeout=15)
    else:
        with photo_source.open("rb") as f:
            response = requests.post(url, data=data, files={"photo": f}, timeout=30)
    response.raise_for_status()
    photo_sizes = (response.json().get("result") or {}).get("photo") or []
    return photo_sizes[-1]["file_id"] if photo_sizes else None


def _send_video(telegram_id: int, video_source, caption: str, reply_markup: dict | None = None) -> str | None:
    """
    Odatiy (to'rtburchak) video xabar — masalan uzun tushuntirish videolari uchun.
    Telegram qaytargan `file_id`ni beradi (keshlash uchun). `video_source` haqida
    `_send_photo`dagi kabi: keshlangan file_id (str) yoki Django `FieldFile`.
    """
    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendVideo")
    data = {"chat_id": telegram_id, "caption": caption, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if isinstance(video_source, str):
        data["video"] = video_source
        response = requests.post(url, data=data, timeout=15)
    else:
        with video_source.open("rb") as f:
            response = requests.post(url, data=data, files={"video": f}, timeout=60)
    response.raise_for_status()
    video_payload = (response.json().get("result") or {}).get("video") or {}
    return video_payload.get("file_id")


def _send_video_note(telegram_id: int, video_source) -> str | None:
    """
    Telegramning 'dumaloq video xabar' (video note) formati — Telegram bu videoni
    mijoz ilovasida avtomatik doira (circle) shaklida ko'rsatadi, buning uchun bizga
    videoni o'zimiz doiraga aylantirish shart emas: sendVideoNote metodi kifoya.
    Eslatma: Telegram talabi — video kvadrat (1:1) va uzunligi <= 60 soniya bo'lishi kerak,
    aks holda Telegram serveri xabarni rad etishi yoki noto'g'ri ko'rsatishi mumkin.
    Caption (matn) video note bilan birga YUBORILMAYDI — Telegram API buni qo'llab-quvvatlamaydi,
    shuning uchun matn alohida xabar sifatida video notedan keyin yuboriladi (tasks.py'da).

    `video_source` — keshlangan file_id (str) yoki Django `FieldFile`; qaytargan
    natija ustidagi kabi keshlash uchun `file_id` qaytaradi.
    """
    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendVideoNote")
    data = {"chat_id": telegram_id}
    if isinstance(video_source, str):
        data["video_note"] = video_source
        response = requests.post(url, data=data, timeout=15)
    else:
        with video_source.open("rb") as f:
            response = requests.post(url, data=data, files={"video_note": f}, timeout=60)
    response.raise_for_status()
    video_note_payload = (response.json().get("result") or {}).get("video_note") or {}
    return video_note_payload.get("file_id")


def _url_button(text: str, url: str) -> dict:
    return {"inline_keyboard": [[{"text": text, "url": url}]]}


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_payment_success(self, telegram_user_id: int, payment_id: int):
    """
    5-6-bosqich: to'lov muvaffaqiyatli bo'lgach mijozga xabar + asosiy menyu (7-rasm).
    Celery task chunki bu webhook view ichidan chaqiriladi va Telegram javobini kutib
    webhookni sekinlashtirmaslik kerak.
    """
    try:
        user = TelegramUser.objects.get(id=telegram_user_id)
        _send_message(
            user.telegram_id,
            "✅ To'lov muvaffaqiyatli qabul qilindi! Akademiyaga xush kelibsiz.\n\n"
            "Quyidagi /start buyrug'i orqali shaxsiy menyungizga o'ting.",
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_payment_failed(self, telegram_user_id: int, reason: str):
    try:
        user = TelegramUser.objects.get(id=telegram_user_id)
        _send_message(
            user.telegram_id,
            "❌ Avtomatik to'lovni amalga oshirib bo'lmadi.\n"
            "Iltimos, karta balansini tekshiring yoki botdagi 'Obuna holati' bo'limidan "
            "kartangizni yangilang.",
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_subscription_expired(self, telegram_user_id: int):
    try:
        user = TelegramUser.objects.get(id=telegram_user_id)
        _send_message(
            user.telegram_id,
            "⛔️ Obunangiz muddati tugadi va siz yopiq kanaldan chiqarib yuborildingiz.\n"
            "Qayta qo'shilish uchun /start buyrug'ini bosing.",
        )
        # TODO(prod): Telegram Bot API banChatMember + unbanChatMember orqali kanaldan chiqarish
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_upcoming_payment(self, telegram_user_id: int, next_date: str):
    try:
        user = TelegramUser.objects.get(id=telegram_user_id)
        _send_message(
            user.telegram_id,
            f"ℹ️ Eslatma: {next_date} sanasida obunangiz uchun avtomatik to'lov amalga oshiriladi.",
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)
