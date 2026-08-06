# JOYLASHTIRISH MANZILI: ACADEMY_BACK/bot/handlers/subscription.py

import uuid
from datetime import timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, Subscription, PendingCheckout
from cms.bot_texts import get_bot_text
from cms.models import BotLink
from bot.keyboards import tariff_select_keyboard, payment_method_keyboard
from subscriptions.services.payme_client import PaymeClient
from subscriptions.services.tribute_client import TributeClient

router = Router()

CHECKOUT_TTL_MINUTES = 15  # 2, 7-rasmdagi "To'lov qilish havolasi muddati" taymeri
# Payme mini app havolasi uchun: mijoz to'lov usuli sahifasida to'xtab qolib, ancha vaqt
# (masalan bir necha soat/kun) o'tgach qaytib kelsa ham havola ishlashi kerak — shu sababli
# bu checkout amalda "doimiy" (uzoq muddatli) qilib yaratiladi, 15 daqiqalik TTL EMAS.
PAYME_LINK_TTL_DAYS = 3650


@router.callback_query(F.data == "join_academy")
async def on_join_academy(callback: CallbackQuery):
    """3-rasm -> 4-rasm: 'Akademiyaga qo'shilish' bosilganda tariflar ko'rsatiladi."""
    text = await _render_tariff_text()
    await callback.message.answer(text, reply_markup=await tariff_select_keyboard())
    await callback.answer()


@router.callback_query(F.data == "back_to_offer")
async def on_back_to_offer(callback: CallbackQuery):
    """4-rasm -> 3-rasm: tarif tanlash sahifasidagi 'Orqaga' — taklif (offer) sahifasiga qaytadi.

    Taklif sahifasi video bilan kelishi mumkin bo'lgani uchun (offer_intro), 'join_academy'
    bosqichi qanday qilingan bo'lsa xuddi shunday — mavjud xabar edit qilinmaydi, yangi
    xabar sifatida qayta yuboriladi.
    """
    from bot.keyboards import join_academy_keyboard
    from cms.services import asend_group_step

    await asend_group_step(callback.message, "payment", "offer_intro", reply_markup=join_academy_keyboard())
    await callback.answer()


@router.callback_query(F.data == "back_to_tariffs")
async def on_back_to_tariffs(callback: CallbackQuery):
    text = await _render_tariff_text()
    await callback.message.edit_text(text, reply_markup=await tariff_select_keyboard())
    await callback.answer()


async def _render_tariff_text() -> str:
    template = get_bot_text("tariff_select")
    lines = []
    async for plan in SubscriptionPlan.objects.filter(is_active=True).order_by("position"):
        lines.append(f"{plan.title} – {plan.price_uzs:,.0f} so'm (Chet el uchun - ${plan.price_usd})")
    return template.replace("{plan_lines}", "\n\n".join(lines))


@router.callback_query(F.data.startswith("select_plan:"))
async def on_select_plan(callback: CallbackQuery):
    """4-rasm -> 5-rasm: tarif tanlangach to'lov usuli tanlash matni.

    'Uzcard/Humo' va 'Chet eldan to'lash' tugmalari shu yerdayoq to'g'ridan-to'g'ri
    tegishli to'lov sahifasiga olib boradi — bosilgan zahoti darhol to'lov sahifasi
    ochiladi, qo'shimcha bosqich/xabar bo'lmaydi. 'Uzcard/Humo' xavfsizlik va doimiy
    ishlash muddati uchun Telegram mini app (web_app) sifatida ochiladi (bug fix:
    ilgari oddiy url tugma + 15 daqiqalik token bo'lgani sababli mijoz kechikib
    bossa havola ishlamay qolardi).
    """
    plan_id = int(callback.data.split(":")[1])
    plan = await SubscriptionPlan.objects.aget(id=plan_id)
    from users.models import TelegramUser
    user = await TelegramUser.objects.aget(telegram_id=callback.from_user.id)

    payme_checkout = await PendingCheckout.objects.acreate(
        checkout_uuid=uuid.uuid4(),
        user=user,
        plan=plan,
        provider=Subscription.Provider.PAYME,
        purpose="new_subscription",
        # Mini app (web_app) tugmasi orqali ochiladi — mijoz istalgan payt (hatto bir necha
        # soat/kun keyin) qaytib bosishi mumkin, shuning uchun 15 daqiqalik TTL emas.
        expires_at=timezone.now() + timedelta(days=PAYME_LINK_TTL_DAYS),
    )
    tribute_checkout = await PendingCheckout.objects.acreate(
        checkout_uuid=uuid.uuid4(),
        user=user,
        plan=plan,
        provider=Subscription.Provider.TRIBUTE,
        purpose="new_subscription",
        expires_at=timezone.now() + timedelta(minutes=CHECKOUT_TTL_MINUTES),
    )

    payme_url = PaymeClient().build_payment_form_url(payme_checkout.checkout_uuid, kind="payment")
    tribute_url = TributeClient().build_subscription_link(
        plan_external_id=f"plan{plan.id}", checkout_uuid=str(tribute_checkout.checkout_uuid)
    )

    offer_link = await BotLink.objects.filter(key=BotLink.Key.OFFER_DOCUMENT).values_list("url", flat=True).afirst()
    template = get_bot_text("payment_method_select")
    text = (
        template
        .replace("{plan_title}", plan.title)
        .replace("{price_uzs}", f"{plan.price_uzs:,.0f}")
        .replace("{price_usd}", str(plan.price_usd))
        .replace("{offer_link}", offer_link or "")
    )
    await callback.message.edit_text(
        text,
        reply_markup=payment_method_keyboard(payme_url, tribute_url),
        disable_web_page_preview=True,
    )
    await callback.answer()