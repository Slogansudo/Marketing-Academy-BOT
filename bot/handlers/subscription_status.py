# JOYLASHTIRISH MANZILI: ACADEMY_BACK/bot/handlers/subscription_status.py

import uuid
from datetime import timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery
from django.utils import timezone

from subscriptions.models import Subscription, PendingCheckout
from cms.bot_texts import get_bot_text
from cms.services import asend_trailing_customs
from bot.keyboards import (
    subscription_status_keyboard, autopay_cancel_confirm_keyboard, card_change_keyboard, checkout_link_keyboard,
)
from subscriptions.services.subscription_service import cancel_auto_renew
from subscriptions.services.payme_client import PaymeClient
from subscriptions.services.tribute_client import TributeClient

router = Router()


@router.callback_query(F.data == "subscription_status")
async def on_subscription_status(callback: CallbackQuery):
    """15-rasm: obuna holati matni — hammasi bazadan dinamik olinadi."""
    from users.models import TelegramUser
    user = await TelegramUser.objects.aget(telegram_id=callback.from_user.id)
    subscription = await Subscription.objects.select_related("card").filter(user=user).afirst()

    if subscription is None:
        await callback.answer("Sizda hali faol obuna yo'q.", show_alert=True)
        return

    template = get_bot_text("subscription_status")
    status_label = "✅ Faol" if subscription.status == Subscription.Status.ACTIVE else subscription.get_status_display()
    autopay_label = "✅ Yoqilgan" if subscription.auto_renew else "❌ O'chirilgan"
    masked_pan = subscription.card.masked_pan if subscription.card else "—"
    next_date = subscription.next_payment_date.strftime("%d.%m.%Y") if subscription.next_payment_date else "—"

    text = (
        template.replace("{status}", status_label)
        .replace("{next_date}", next_date)
        .replace("{autopay}", autopay_label)
        .replace("{masked_pan}", masked_pan)
    )
    await callback.message.edit_text(text, reply_markup=await subscription_status_keyboard())
    await asend_trailing_customs(
        callback.message, "main_menu", "subscription_status",
        context={
            "status": status_label, "next_date": next_date,
            "autopay": autopay_label, "masked_pan": masked_pan,
        },
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_autopay")
async def on_toggle_autopay(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚠️ Haqiqatdan ham obunani bekor qilmoqchimisiz?\n\n"
        "Bekor qilsangiz, kartangizdan keyingi to'lov yechilmaydi. "
        "Obuna joriy muddat oxirigacha faol qoladi.",
        reply_markup=autopay_cancel_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "autopay_cancel_confirm")
async def on_autopay_cancel_confirm(callback: CallbackQuery):
    from users.models import TelegramUser
    from asgiref.sync import sync_to_async

    user = await TelegramUser.objects.aget(telegram_id=callback.from_user.id)
    await sync_to_async(cancel_auto_renew)(user)
    await callback.answer("Avtomatik to'lov bekor qilindi ✅", show_alert=True)
    await on_subscription_status(callback)


CARD_REPLACEMENT_LINK_TTL_DAYS = 3650  # Payme mini app tugmasi uchun amalda "doimiy" token


@router.callback_query(F.data == "change_card")
async def on_change_card(callback: CallbackQuery):
    """
    'Kartani almashtirish' bosildi -> tushuntirish matni + 'Davom etish'.

    Payme bo'lsa, 'Davom etish' tugmasi qo'shimcha oraliq xabarsiz to'g'ridan-to'g'ri karta
    almashtirish mini app (web_app) sahifasini ochadi — checkout shu yerdayoq DOIMIY (uzoq
    muddatli) token bilan oldindan yaratiladi, shunda mijoz istalgan payt (hatto ancha
    vaqtdan keyin ham) shu tugmani bossa havola ishlaydi.
    Tribute bo'lsa, eski ikki bosqichli (callback -> yangi xabar) oqim saqlanadi.
    """
    from users.models import TelegramUser
    user = await TelegramUser.objects.aget(telegram_id=callback.from_user.id)
    subscription = await Subscription.objects.select_related("plan").aget(user=user)

    template = get_bot_text("card_change_intro")
    next_date = subscription.next_payment_date.strftime("%d.%m.%Y") if subscription.next_payment_date else "—"
    text = (
        template.replace("{plan_title}", subscription.plan.title)
        .replace("{price}", f"{subscription.plan.price_uzs:,.0f}")
        .replace("{next_date}", next_date)
    )

    mini_app_url = None
    if subscription.provider == Subscription.Provider.PAYME:
        checkout = await PendingCheckout.objects.acreate(
            checkout_uuid=uuid.uuid4(),
            user=user,
            plan=subscription.plan,
            provider=subscription.provider,
            purpose="card_change",
            expires_at=timezone.now() + timedelta(days=CARD_REPLACEMENT_LINK_TTL_DAYS),
        )
        mini_app_url = PaymeClient().build_payment_form_url(checkout.checkout_uuid, kind="card-replacement")

    await callback.message.edit_text(text, reply_markup=card_change_keyboard(mini_app_url))
    await asend_trailing_customs(
        callback.message, "main_menu", "card_change_intro",
        context={"plan_title": subscription.plan.title, "price": f"{subscription.plan.price_uzs:,.0f}", "next_date": next_date},
    )
    await callback.answer()


@router.callback_query(F.data == "card_change_continue")
async def on_card_change_continue(callback: CallbackQuery):
    """
    Faqat Tribute uchun qoladi ('Davom etish' bosildi): Tribute obuna boshqaruv sahifasiga
    yo'naltiriladi. Payme uchun bu endi ishlatilmaydi — havola to'g'ridan-to'g'ri
    'Davom etish' tugmasida mini app sifatida beriladi (qarang on_change_card).
    """
    from users.models import TelegramUser
    user = await TelegramUser.objects.aget(telegram_id=callback.from_user.id)
    subscription = await Subscription.objects.select_related("plan").aget(user=user)

    checkout = await PendingCheckout.objects.acreate(
        checkout_uuid=uuid.uuid4(),
        user=user,
        plan=subscription.plan,
        provider=subscription.provider,
        purpose="card_change",
        expires_at=timezone.now() + timedelta(minutes=15),
    )

    client = TributeClient()
    url = client.build_subscription_link(plan_external_id=f"plan{subscription.plan_id}", checkout_uuid=str(checkout.checkout_uuid))

    await callback.message.answer(
        "Yangi karta ma'lumotlarini kiritish uchun havolani oching:",
        reply_markup=checkout_link_keyboard(url, "💳 Kartani bog'lash"),
    )
    await callback.answer()