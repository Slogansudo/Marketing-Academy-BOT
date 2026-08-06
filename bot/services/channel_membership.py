# JOYLASHTIRISH MANZILI: ACADEMY_BACK/bot/services/channel_membership.py

"""
Yopiq kanaldan avtomatik chiqarib yuborish. Obuna muddati tugagan/bekor
qilingan (kaskad tugagan) foydalanuvchi shu funksiya orqali kanaldan
chiqariladi.

Sync, xom (`requests`) Telegram HTTP API chaqiruvi — `cms.services.send_raw_with_media`
bilan bir xil uslub, chunki bu funksiya ham aiogram konteksti bo'lmagan joylardan
(Celery/`renewal_engine.py`) chaqiriladi.
"""

import logging

import requests
from django.conf import settings

from cms.models import ChannelSettings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def kick_user_from_private_channel(telegram_id: int) -> None:
    """
    `banChatMember` + darhol `unbanChatMember` (aks holda foydalanuvchi kanalga
    QAYTA QO'SHILA OLMAYDI — Telegramda ban doimiy, faqat unban qilingandan
    keyin foydalanuvchi yangi taklif havolasi orqali qayta kira oladi).

    `ChannelSettings.auto_kick_on_expiry=False` bo'lsa yoki `channel_chat_id`
    hali sozlanmagan bo'lsa — hech narsa qilinmaydi (jim o'tkazib yuboriladi,
    xatolik ko'tarilmaydi, chunki bu funksiya to'lov/kaskad oqimini
    to'xtatmasligi kerak).
    """
    channel_settings = ChannelSettings.load()
    if not channel_settings.auto_kick_on_expiry or not channel_settings.channel_chat_id:
        return

    chat_id = channel_settings.channel_chat_id

    try:
        ban_url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method="banChatMember")
        response = requests.post(ban_url, json={"chat_id": chat_id, "user_id": telegram_id}, timeout=10)
        response.raise_for_status()

        unban_url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN, method="unbanChatMember")
        response = requests.post(
            unban_url, json={"chat_id": chat_id, "user_id": telegram_id, "only_if_banned": True}, timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        # Foydalanuvchi allaqachon kanalda bo'lmasligi (masalan o'zi chiqib ketgan)
        # yoki bot admin huquqini yo'qotgan bo'lishi mumkin — bu holatlar to'lov/
        # kaskad oqimini to'xtatmasligi kerak, shuning uchun faqat log yoziladi.
        logger.warning("Kanaldan chiqarib yuborishda xatolik: telegram_id=%s, chat_id=%s", telegram_id, chat_id, exc_info=True)
