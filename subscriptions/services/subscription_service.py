# JOYLASHTIRISH MANZILI: ACADEMY_BACK/subscriptions/services/subscription_service.py

import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from subscriptions.models import Subscription, Payment, PendingCheckout, PaymentCard
from gifts.models import UserGiftProgress
from growth.services import register_sale

logger = logging.getLogger(__name__)


async def user_has_active_subscription(user) -> bool:
    """
    Bot menyusini (Yopiq kanalga qo'shilish / Shaxsiy kabinet / Obuna holati / Yordam)
    ko'rsatishdan oldin shu tekshiruv ishlatiladi: ro'yxatdan o'tgan bo'lsa ham, hali
    tarif tanlab to'lov qilmagan (yoki obunasi tugagan) foydalanuvchiga bu menyu
    HECH QACHON ko'rsatilmasligi kerak.

    CANCELLED holati ham "faol" hisoblanadi, chunki avtomatik to'lov o'chirilgan bo'lsa-da,
    obuna joriy muddat oxirigacha amal qiladi (kanalga kirish huquqi saqlanadi).
    """
    return await Subscription.objects.filter(
        user=user,
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.CANCELLED],
    ).aexists()


@transaction.atomic
def activate_or_renew_subscription(
    pending_checkout: PendingCheckout,
    external_transaction_id: str,
    masked_pan: str | None = None,
    payme_card_token: str | None = None,
) -> Payment:
    """
    5-6-bosqich markazi: Payme yoki Tribute webhookidan kelgan muvaffaqiyatli to'lovni
    Subscription/Payment/UserGiftProgress ga aylantiradi.

    - Agar bu birinchi to'lov bo'lsa -> Subscription yaratiladi/faollashtiriladi.
    - next_payment_date = bugun + plan.duration_months (1 oylikda har oy, 3 oylikda har 3 oyda
      yechiladi degan 6-bosqich logikasi shu yerda amalga oshadi).
    - UserGiftProgress.current_streak_months +1 qilinadi (uzluksiz to'lov sovg'a zinapoyasi).
    """
    # Poyga holatidan himoya: bir xil pending_checkout uchun ikkita webhook chaqiruvi
    # (masalan Tribute/Payme'ning qayta yuborishi natijasida) bir vaqtda kelib qolsa,
    # ikkalasi ham `is_used=False` deb o'qib, ikkitasi ham ishlov berib yuborishi mumkin edi.
    # Qatorni qulflab, qayta yuklab, `is_used` holatini qulf ostida qayta tekshiramiz.
    pending_checkout = PendingCheckout.objects.select_for_update().get(id=pending_checkout.id)
    if pending_checkout.is_used:
        logger.info(
            "PendingCheckout %s allaqachon ishlangan (dublikat webhook) — qayta ishlov berilmadi.",
            pending_checkout.checkout_uuid,
        )
        existing_payment = Payment.objects.filter(
            subscription__user=pending_checkout.user,
            external_transaction_id=external_transaction_id,
        ).first()
        if existing_payment is not None:
            return existing_payment
        # Payment topilmasa ham (masalan turli id formatlari), obunani qayta faollashtirib/
        # muddatni qayta uzaytirib yubormaslik uchun eng so'nggi Payment qaytariladi.
        return Payment.objects.filter(subscription__user=pending_checkout.user).first()

    user = pending_checkout.user
    plan = pending_checkout.plan

    card = None
    if pending_checkout.provider == Subscription.Provider.PAYME and masked_pan and payme_card_token:
        card, _ = PaymentCard.objects.update_or_create(
            user=user,
            payme_card_token=payme_card_token,
            defaults={"masked_pan": masked_pan, "is_primary": True},
        )
        # Yangi asosiy karta belgilanganda eski kartalarni is_primary=False qilamiz (kartani almashtirish uchun)
        PaymentCard.objects.filter(user=user).exclude(id=card.id).update(is_primary=False)

    subscription, _ = Subscription.objects.get_or_create(user=user, defaults={"plan": plan, "provider": pending_checkout.provider})
    subscription.plan = plan
    subscription.provider = pending_checkout.provider
    subscription.status = Subscription.Status.ACTIVE
    subscription.auto_renew = True
    subscription.started_at = subscription.started_at or timezone.now()
    subscription.next_payment_date = date.today() + relativedelta(months=plan.duration_months)
    # Narxni "muzlatish": bu funksiya faqat mijoz o'zi ONGLI ravishda tarif tanlab to'lov
    # qilgan paytda chaqiriladi (yangi obuna YOKI bekor/tugagandan keyin qaytadan sotib olish) —
    # avtomatik kaskad (renewal_engine.py) bu yerga UMUMAN kirmaydi. Shu sabab bu — narxni
    # qayta belgilash uchun to'g'ri va yagona joy: shu paytdagi joriy plan narxi
    # `locked_price_*`ga yozib qo'yiladi, va KEYINGI barcha avtomatik to'lovlar (mijoz hech
    # narsa qilmasa ham) shu qiymatdan foydalanadi — hatto admin keyinchalik shu plan narxini
    # oshirsa/tushirsa ham, mijoz obuna shartlarini buzmaguncha eski narxda qolaveradi.
    subscription.locked_price_uzs = plan.price_uzs
    subscription.locked_price_usd = plan.price_usd
    if card:
        subscription.card = card
    if pending_checkout.provider == Subscription.Provider.TRIBUTE:
        subscription.tribute_external_id = external_transaction_id
    subscription.save()

    is_recurring = Payment.objects.filter(subscription=subscription, status=Payment.Status.SUCCESS).exists()
    payment = Payment.objects.create(
        subscription=subscription,
        amount=subscription.locked_price_uzs if pending_checkout.provider == Subscription.Provider.PAYME else subscription.locked_price_usd,
        currency="UZS" if pending_checkout.provider == Subscription.Provider.PAYME else "USD",
        provider=pending_checkout.provider,
        status=Payment.Status.SUCCESS,
        external_transaction_id=external_transaction_id,
        is_recurring_charge=is_recurring,
        paid_at=timezone.now(),
    )

    progress, _ = UserGiftProgress.objects.get_or_create(user=user)
    progress.register_successful_payment()

    if not is_recurring:
        # Reklama kampaniyasi statistikasi: bu foydalanuvchining birinchi (ongli) to'lovi —
        # agar u referal havola orqali kirgan bo'lsa, o'sha havolaning sotuv sonini +1 qilamiz.
        register_sale(user.referral_source)

    pending_checkout.is_used = True
    pending_checkout.save(update_fields=["is_used"])

    return payment


@transaction.atomic
def complete_pending_checkout(
    pending_checkout: PendingCheckout,
    external_transaction_id: str,
    masked_pan: str,
    payme_card_token: str,
) -> Payment | PaymentCard:
    """
    pay.turdievakademiyasi.uz formasi (cards.verify + kerak bo'lsa receipts.pay muvaffaqiyatli
    bo'lgandan keyin) shu funksiyani chaqiradi. `purpose`ga qarab uchta yo'ldan biriga boradi —
    bu mantiq ilgari faqat Payme webhookida (`webhooks.py:handle_PerformTransaction`) bo'lgan,
    endi ikkalasi ham shu yerga tayanadi (kod takrorlanmasin uchun).
    """
    if pending_checkout.purpose == "new_subscription":
        payment = activate_or_renew_subscription(
            pending_checkout=pending_checkout,
            external_transaction_id=external_transaction_id,
            masked_pan=masked_pan,
            payme_card_token=payme_card_token,
        )
        from bot.services.notifier import notify_payment_success
        notify_payment_success.delay(payment.subscription.user_id, payment.id)
        return payment

    if pending_checkout.purpose == "card_change":
        card = replace_primary_card(pending_checkout.user, masked_pan, payme_card_token)
        pending_checkout.is_used = True
        pending_checkout.save(update_fields=["is_used"])
        return card

    if pending_checkout.purpose == "renewal_card_update":
        card = replace_primary_card(pending_checkout.user, masked_pan, payme_card_token)
        pending_checkout.is_used = True
        pending_checkout.save(update_fields=["is_used"])

        cycle = pending_checkout.renewal_cycle
        if cycle and not cycle.is_terminal:
            from subscriptions.services.renewal_engine import execute_renewal_attempt
            execute_renewal_attempt.delay(cycle.id, expected_attempt_number=cycle.attempt_number)
        return card

    raise ValueError(f"Noma'lum PendingCheckout.purpose: {pending_checkout.purpose}")


@transaction.atomic
def replace_primary_card(user, masked_pan: str, payme_card_token: str) -> PaymentCard:
    """15-bosqich: 'Kartani almashtirish' — hozirgi to'lov davri tugamaguncha eski kartadan pul yechilmaydi,
    keyingi avto to'lov yangi kartadan amalga oshadi."""
    PaymentCard.objects.filter(user=user).update(is_primary=False)
    card = PaymentCard.objects.create(user=user, masked_pan=masked_pan, payme_card_token=payme_card_token, is_primary=True)
    Subscription.objects.filter(user=user).update(card=card)
    return card


@transaction.atomic
def _renew_from_recurring(subscription: Subscription, external_transaction_id: str) -> Payment:
    """
    Tribute'dan kelgan `recurring_payment` eventi uchun: PendingCheckout endi yo'q (mijoz
    hech qanday tugma bosmagan, to'lov avtomatik Tribute tomonida sodir bo'lgan), shuning
    uchun mavjud Subscription to'g'ridan-to'g'ri yangilanadi.

    MUHIM (idempotentlik): haqiqiy pul yechish to'liq Tribute tomonida sodir bo'ladi — biz uni
    qayta amalga oshira olmaymiz va oshirmaymiz ham. Lekin Tribute WEBHOOKNI qayta yuborishi
    mumkin (masalan bizning javobimiz sekin kelsa yoki tarmoqda vaqtinchalik uzilish bo'lsa —
    ko'pchilik webhook provayderlari "kamida bir marta" kafolatini beradi, aynan bir marta emas).
    Agar shu himoya bo'lmasa, BIR XIL haqiqiy to'lov uchun bu funksiya ikki marta chaqirilganda
    mijozning obuna muddati ikki marta uzayib ketadi va ikkita SUCCESS Payment yozuvi paydo
    bo'ladi — garchi Tribute'da faqat bitta pul yechilgan bo'lsa ham.

    Shu sabab: (1) subscription qatori `select_for_update()` bilan qulflanadi — bir xil
    obuna uchun ikkita parallel webhook chaqiruvi ketma-ket ishlaydi; (2) shu qulf ostida
    avval xuddi shu `external_transaction_id` bilan Payment allaqachon yozilganmi tekshiriladi —
    agar ha bo'lsa, hech qanday yangi yozuv/muddat uzaytirish qilinmasdan mavjud Payment qaytariladi.
    """
    if not external_transaction_id:
        raise ValueError("Tribute recurring_payment eventida payment_id topilmadi")

    subscription = Subscription.objects.select_for_update().get(id=subscription.id)

    existing = Payment.objects.filter(
        subscription=subscription,
        provider=Subscription.Provider.TRIBUTE,
        external_transaction_id=external_transaction_id,
    ).first()
    if existing is not None:
        logger.info(
            "Tribute recurring_payment dublikat: subscription=%s, external_transaction_id=%s — "
            "allaqachon ishlangan, muddat qayta uzaytirilmadi va yangi Payment yaratilmadi.",
            subscription.id, external_transaction_id,
        )
        return existing

    plan = subscription.plan
    subscription.status = Subscription.Status.ACTIVE
    subscription.next_payment_date = date.today() + relativedelta(months=plan.duration_months)
    subscription.save(update_fields=["status", "next_payment_date"])

    # Bu — AVTOMATIK (recurring) to'lov, mijoz hech narsa tanlamagan, shuning uchun narx
    # bu yerda QAYTA MUZLATILMAYDI (`locked_price_usd` o'zgartirilmaydi) — faqat birinchi
    # xariddagi (yoki qayta obuna bo'lgandagi) muzlatilgan narx o'qiladi. Eski (bu maydon
    # qo'shilishidan OLDIN yaratilgan) obunalar uchun xavfsiz fallback — joriy plan narxi.
    charge_amount = subscription.locked_price_usd if subscription.locked_price_usd is not None else plan.price_usd

    payment = Payment.objects.create(
        subscription=subscription,
        amount=charge_amount,
        currency="USD",
        provider=Subscription.Provider.TRIBUTE,
        status=Payment.Status.SUCCESS,
        external_transaction_id=external_transaction_id,
        is_recurring_charge=True,
        paid_at=timezone.now(),
    )

    progress, _ = UserGiftProgress.objects.get_or_create(user=subscription.user)
    progress.register_successful_payment()
    return payment


def cancel_auto_renew(user) -> Subscription:
    """15-bosqich: 'Avtomatik to'lov' -> ha bosilganda. Muddat oxirigacha faol qoladi, keyin yechilmaydi."""
    subscription = Subscription.objects.get(user=user)
    subscription.auto_renew = False
    subscription.status = Subscription.Status.CANCELLED
    subscription.save(update_fields=["auto_renew", "status"])
    return subscription