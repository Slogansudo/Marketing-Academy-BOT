# JOYLASHTIRISH MANZILI: ACADEMY_BACK/bot/handlers/renewal.py

import uuid
from datetime import timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery
from django.utils import timezone

from subscriptions.models import Subscription, SubscriptionRenewalCycle, PendingCheckout
from subscriptions.services.renewal_engine import execute_renewal_attempt
from subscriptions.services.payme_client import PaymeClient
from cms.bot_texts import get_bot_text
from cms.services import asend_cascade_stage
from bot.keyboards import tariff_select_keyboard, renewal_card_change_keyboard

router = Router()

# Renewal kaskadi faqat Payme uchun ishlaydi (Tribute o'z recurring to'lovini o'zi boshqaradi).
# Mini app tugmasi orqali ochilgani uchun token amalda "doimiy" (uzoq muddatli) qilinadi —
# mijoz karta muddati o'tgani haqidagi eslatmani darhol ko'rmasa ham, keyinroq qaytib
# 'Davom etish'ni bossa havola baribir ishlaydi.
CARD_REPLACEMENT_LINK_TTL_DAYS = 3650


@router.callback_query(F.data.startswith("renewal_continue:"))
async def on_renewal_continue(callback: CallbackQuery):
    """
    17-18-bosqich: 'Davom etish' bosildi. Alert ko'rsatiladi va DARHOL qayta urinish
    navbatga qo'yiladi. `expected_attempt_number` joriy bazadagi qiymat bilan uzatiladi —
    shu orqali agar aynan shu payt rejalashtirilgan avto-urinish ham ishga tushib qolsa,
    ikkalasidan faqat BITTASI haqiqiy to'lovni amalga oshiradi (18-bosqich kafolati).
    """
    alert_text = get_bot_text("renewal_processing_alert")
    await callback.answer(alert_text, show_alert=True)

    cycle_id = int(callback.data.split(":")[1])
    cycle = await SubscriptionRenewalCycle.objects.aget(id=cycle_id)
    if cycle.is_terminal:
        return  # allaqachon yakunlangan — qayta urinishga hojat yo'q

    execute_renewal_attempt.delay(cycle.id, expected_attempt_number=cycle.attempt_number)


@router.callback_query(F.data.startswith("renewal_change_card:"))
async def on_renewal_change_card(callback: CallbackQuery):
    """
    Karta muddati o'tgani sababli 'Kartani almashtirish' bosildi -> tushuntirish matni +
    'Davom etish'. Checkout (va uning mini app havolasi) shu yerdayoq DOIMIY token bilan
    oldindan yaratiladi va to'g'ridan-to'g'ri 'Davom etish' tugmasiga (web_app) qo'yiladi —
    qo'shimcha oraliq bosqich/xabar yo'q, karta yangilash sahifasi Telegram mini app
    sifatida ochiladi.
    """
    cycle_id = int(callback.data.split(":")[1])
    cycle = await SubscriptionRenewalCycle.objects.select_related("subscription__user", "subscription__plan").aget(id=cycle_id)
    subscription = cycle.subscription

    context = {"tarif_name": subscription.plan.title, "amount": f"{subscription.plan.price_uzs:,.0f}"}

    checkout = await PendingCheckout.objects.acreate(
        checkout_uuid=uuid.uuid4(),
        user=subscription.user,
        plan=subscription.plan,
        provider=Subscription.Provider.PAYME,
        purpose="renewal_card_update",
        renewal_cycle=cycle,
        expires_at=timezone.now() + timedelta(days=CARD_REPLACEMENT_LINK_TTL_DAYS),
    )
    # Karta yangilashda darhol summa yechilmaydi — verify muvaffaqiyatli bo'lgach
    # complete_pending_checkout avtomatik yangi kartadan ushbu billing davri uchun qayta urinadi
    # (purpose=renewal_card_update -> execute_renewal_attempt.delay(...)).
    mini_app_url = PaymeClient().build_payment_form_url(checkout.checkout_uuid, kind="card-replacement")

    await asend_cascade_stage(
        callback.message,
        trigger_event="card_change_requested",
        context=context,
        reply_markup=renewal_card_change_keyboard(mini_app_url),
    )
    await callback.answer()


@router.callback_query(F.data == "renewal_reactivate")
async def on_renewal_reactivate(callback: CallbackQuery):
    """
    17-bosqich yakuni: obuna butunlay to'xtatilgandan keyin 'Obuna tiklash' bosilsa,
    mijoz xuddi yangi mijozdek qaytadan tarif tanlash bosqichidan o'tadi
    (bosqich/daraja allaqachon 'boshlovchi'ga tushirilgan — gifts.UserGiftProgress.reset_streak).
    """
    text = "Akademiyaga qayta qo'shilish uchun obuna muddatini tanlang 👇🏻"
    await callback.message.answer(text, reply_markup=await tariff_select_keyboard())
    await callback.answer()