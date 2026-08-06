from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)
from django.conf import settings

from subscriptions.models import SubscriptionPlan
from cms.models import BotLink


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    """2-bosqich: 'Telefon raqamni yuborish' pastki tugmasi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def join_academy_keyboard() -> InlineKeyboardMarkup:
    """3-rasm: 'Akademiyaga qo'shilish' tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Akademiyaga qo'shilish", callback_data="join_academy")]
    ])


async def tariff_select_keyboard() -> InlineKeyboardMarkup:
    """4-rasm: obuna muddatlari (admin panelda qo'shilgan barcha faol tariflar, position bo'yicha)."""
    rows = []
    async for plan in SubscriptionPlan.objects.filter(is_active=True).order_by("position"):
        rows.append([InlineKeyboardButton(text=plan.title, callback_data=f"select_plan:{plan.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_offer")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_method_keyboard(payme_url: str, tribute_url: str) -> InlineKeyboardMarkup:
    """5-rasm: 'Uzcard/Humo' va 'Chet eldan to'lash' tugmalari.

    'Uzcard/Humo' — bizning pay.turdievakademiyasi.uz sahifamiz, xavfsizlik va cheksiz
    amal qilish muddati uchun Telegram mini app (web_app) sifatida ochiladi: shunday qilib
    checkout havolasi qancha vaqt oldin yuborilgan bo'lishidan qat'i nazar (hatto bir necha
    soat/kun keyin ham) mijoz uni bosganda to'lov sahifasi doim ishlaydi.
    'Chet eldan to'lash' — Tribute'ning o'zining t.me mini-app havolasi, allaqachon shu
    tarzda ishlaydi, shu sababli oddiy url tugma sifatida qoladi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Uzcard/Humo", web_app=WebAppInfo(url=payme_url))],
        [InlineKeyboardButton(text="Chet eldan to'lash", url=tribute_url)],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_tariffs")],
    ])


def checkout_link_keyboard(url: str, button_text: str = "💳 To'lovni amalga oshirish") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, url=url)]
    ])


def renewal_card_change_keyboard(mini_app_url: str) -> InlineKeyboardMarkup:
    """To'lov kaskadi ichidagi 'Kartani almashtirish' -> 'Davom etish' — bu kontekstda
    'subscription_status'ga qaytish tugmasi mos emas (obuna hozircha to'xtatilgan bo'lishi
    mumkin), shuning uchun faqat mini app tugmasi beriladi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Davom etish", web_app=WebAppInfo(url=mini_app_url))],
    ])


async def main_menu_keyboard() -> InlineKeyboardMarkup:
    """9-rasm: ishtirokchi menyusi — 4ta tugma, havolalari admin panel (cms.BotLink) dan olinadi."""
    channel_link = await BotLink.objects.filter(key=BotLink.Key.PRIVATE_CHANNEL).values_list("url", flat=True).afirst()
    help_link = await BotLink.objects.filter(key=BotLink.Key.HELP).values_list("url", flat=True).afirst()

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yopiq kanalga qo'shilish", url=channel_link or "https://t.me/")],
        [InlineKeyboardButton(
            text="Shaxsiy kabinet",
            web_app=WebAppInfo(url=settings.MINI_APP_BASE_URL),
        )],
        [InlineKeyboardButton(text="Obuna holati", callback_data="subscription_status")],
        [InlineKeyboardButton(text="Yordam", url=help_link or "https://t.me/")],
    ])


async def subscription_status_keyboard() -> InlineKeyboardMarkup:
    """15-bosqich: obuna holati sahifasidagi 4ta tugma."""
    channel_link = await BotLink.objects.filter(key=BotLink.Key.PRIVATE_CHANNEL).values_list("url", flat=True).afirst()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yopiq kanalga kirish", url=channel_link or "https://t.me/")],
        [InlineKeyboardButton(text="Avtomatik to'lov", callback_data="toggle_autopay")],
        [InlineKeyboardButton(text="Kartani almashtirish", callback_data="change_card")],
        [InlineKeyboardButton(text="⬅️ Menyuga qaytish", callback_data="back_to_menu")],
    ])


def autopay_cancel_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="autopay_cancel_confirm")],
        [InlineKeyboardButton(text="❌ Yo'q", callback_data="subscription_status")],
    ])


def card_change_keyboard(mini_app_url: str | None = None) -> InlineKeyboardMarkup:
    """'Davom etish' tugmasi:
    - Payme bo'lsa `mini_app_url` beriladi -> tugma to'g'ridan-to'g'ri karta almashtirish
      mini app (web_app) sahifasini ochadi, token doimiy bo'lgani uchun istalgan payt ishlaydi.
    - Tribute bo'lsa `mini_app_url=None` -> eski callback oqimi (card_change_continue) ishlatiladi."""
    if mini_app_url:
        continue_button = InlineKeyboardButton(text="Davom etish", web_app=WebAppInfo(url=mini_app_url))
    else:
        continue_button = InlineKeyboardButton(text="Davom etish", callback_data="card_change_continue")
    return InlineKeyboardMarkup(inline_keyboard=[
        [continue_button],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="subscription_status")],
    ])