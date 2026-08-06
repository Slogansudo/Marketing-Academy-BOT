# JOYLASHTIRISH MANZILI: ACADEMY_BACK/subscriptions/services/renewal_engine.py

"""
17-18-bosqich: obuna avto to'lovining to'liq kaskad (cascade) mantig'i.

MUHIM QOIDA (18-bosqich): mijozdan bir marta pul yechilsin, bir necha marta yechib
ketmasin. Bu ikki mexanizm bilan kafolatlanadi:

  1. "Claim" bosqichi qisqa DB tranzaksiyasida `select_for_update()` bilan bajariladi:
     faqat bitta process cycle.attempt_number ni oshira oladi va IN_PROGRESS holatiga
     o'tkaza oladi — parallel ishga tushgan ikkita worker (masalan rejalashtirilgan
     avto-retry va mijozning "Davom etish" bosishi bir vaqtga to'g'ri kelib qolsa ham)
     bir-birini bloklamaydi, lekin faqat BITTASI haqiqiy to'lovni amalga oshiradi.
  2. Har bir kelajakdagi (rejalashtirilgan) urinish `expected_attempt_number` bilan
     chaqiriladi — agar shu vaqtga kelib cycle.attempt_number allaqachon boshqa yo'l
     bilan oshgan bo'lsa (masalan mijoz oldinroq "Davom etish"ni bosgan bo'lsa),
     eskirgan (stale) task hech narsa qilmay chiqib ketadi.
  3. cycle.status SUCCEEDED yoki CANCELLED bo'lsa (`is_terminal`), keyingi HAR QANDAY
     chaqiruv (eski task, qayta bosilgan tugma va h.k.) darhol to'xtaydi.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from subscriptions.models import (
    Subscription, Payment, PaymentCard,
    SubscriptionRenewalCycle, RenewalAttempt,
)
from subscriptions import renewal_config
from subscriptions.services.payme_client import PaymeClient, PaymeError
from gifts.models import UserGiftProgress

logger = logging.getLogger(__name__)


@dataclass
class ChargeResult:
    outcome: str  # "success" | "insufficient_funds" | "card_expired" | "error"
    error_reason: Optional[str] = None
    transaction_id: Optional[str] = None
    receipt_id: Optional[str] = None  # error bo'lsa ham — keyingi urinishdan oldin receipts.check bilan tekshirish uchun


def _effective_price_uzs(subscription: Subscription):
    """
    Avto to'lov kaskadida yechiladigan HAQIQIY summa: mijoz birinchi xarid qilgan (yoki eng
    so'nggi marta ONGLI ravishda qaytadan obuna bo'lgan) paytda `subscription_service.py`
    tomonidan "muzlatilgan" narx (`locked_price_uzs`) — admin panelda shu tarifning narxi
    (`SubscriptionPlan.price_uzs`) keyinchalik oshirilgan/tushirilgan bo'lsa ham, mijoz obuna
    shartlarini buzmaguncha shu eski narxda qolaveradi.

    `locked_price_uzs` bo'sh (`None`) bo'lsa — bu maydon qo'shilishidan OLDIN yaratilgan eski
    obuna, xavfsiz fallback sifatida joriy plan narxi ishlatiladi.
    """
    return subscription.locked_price_uzs if subscription.locked_price_uzs is not None else subscription.plan.price_uzs


def _perform_charge(
    subscription: Subscription, order_id: str, existing_receipt_id: Optional[str] = None,
) -> ChargeResult:
    """
    Haqiqiy Payme chaqiruvi shu yerda amalga oshadi. `order_id` har bir YANGI urinish
    uchun NOYOB (cycle_id + attempt_number asosida) — shu sabab Payme tomonida ham bir
    xil order_id ikki marta yuborilsa, u dublikat sifatida rad etiladi.

    DIQQAT: bu himoya faqat aynan BIR XIL order_id qayta yuborilganda ishlaydi. Agar
    receipts.pay javobi tarmoq xatosi bilan yo'qolib qolsa, chaqiruvchi (execute_renewal_attempt)
    KEYINGI urinishdan oldin avval receipts.check bilan eski chekni tekshiradi — shu funksiya
    faqat "eski chek hali to'lanmagan (yoki bekor qilingan)" deb tasdiqlangandan keyin chaqiriladi,
    yoki umuman birinchi marta yangi chek yaratish uchun ishlatiladi (existing_receipt_id=None).
    """
    if not subscription.card:
        return ChargeResult(outcome="card_expired", error_reason="Bog'langan karta topilmadi")

    client = PaymeClient()
    amount_tiyin = int(_effective_price_uzs(subscription) * 100)
    try:
        transaction_id = client.charge(
            subscription.card.payme_card_token, amount_tiyin, order_id,
            existing_receipt_id=existing_receipt_id,
        )
        return ChargeResult(outcome="success", transaction_id=transaction_id, receipt_id=existing_receipt_id)
    except PaymeError as exc:
        reason_code = getattr(exc, "reason_code", "error")
        receipt_id = getattr(exc, "receipt_id", None)
        if reason_code in ("insufficient_funds", "card_expired"):
            return ChargeResult(outcome=reason_code, error_reason=str(exc), receipt_id=receipt_id)
        return ChargeResult(outcome="error", error_reason=str(exc), receipt_id=receipt_id)
    except NotImplementedError:
        # Payme integratsiyasi hali ulanmagan muhitda (dev/staging) — xato sifatida belgilanadi,
        # lekin cascade shu yerdan buzilmasligi uchun "error" natija qaytariladi.
        return ChargeResult(outcome="error", error_reason="Payme integratsiyasi ulanmagan (dev muhit)")


def _resolve_previous_error_receipt(client: PaymeClient, previous_attempt: "RenewalAttempt") -> Optional[int]:
    """
    Oldingi urinish "error" bilan tugagan VA receipt yaratilgan bo'lsa (ya'ni receipts.pay
    javobi yo'qolgan bo'lishi mumkin bo'lgan holat), Payme'dan uning HAQIQIY holatini so'raydi.

    Qaytaradi:
      - RECEIPT_STATE_PAID (4)      — pul allaqachon yechilgan, YANGI to'lov QILINMASLIGI kerak.
      - RECEIPT_STATE_CANCELLED (50) yoki boshqa yakuniy holat — pul yechilmagan, xavfsiz qayta urinish mumkin.
      - None — Payme bilan aloqa o'rnatib bo'lmadi (masalan yana tarmoq xatosi) — bu holatda
        xavfsizlik uchun bu safar HECH QANDAY yangi to'lov QILINMAYDI (keyingi urinishda yana tekshiriladi).
    """
    try:
        return client.check_receipt(previous_attempt.payme_receipt_id)
    except PaymeError:
        logger.warning(
            "Cycle %s: oldingi chek (%s) holatini receipts.check orqali tekshirib bo'lmadi — "
            "ikki marta pul yechilishining oldini olish uchun bu safar yangi to'lov urinishi "
            "o'tkazib yuborildi. Keyingi urinishda yana tekshiriladi.",
            previous_attempt.cycle_id, previous_attempt.payme_receipt_id,
        )
        return None


def create_due_cycles() -> int:
    """
    17-bosqich: to'lov kuni kelgan (next_payment_date == bugun), PAYME orqali avto to'lovga
    ega bo'lgan barcha obunalar uchun (agar shu kun uchun cycle hali yaratilmagan bo'lsa)
    yangi SubscriptionRenewalCycle ochiladi va birinchi urinish darhol navbatga qo'yiladi.
    """
    today = date.today()
    due_subscriptions = Subscription.objects.filter(
        provider=Subscription.Provider.PAYME,
        status=Subscription.Status.ACTIVE,
        auto_renew=True,
        next_payment_date=today,
    )
    created = 0
    for subscription in due_subscriptions:
        cycle, was_created = SubscriptionRenewalCycle.objects.get_or_create(
            subscription=subscription, due_date=today,
        )
        if was_created:
            created += 1
            execute_renewal_attempt.delay(cycle.id, expected_attempt_number=0)
    return created


@shared_task(bind=True, max_retries=0)
def execute_renewal_attempt(self, cycle_id: int, expected_attempt_number: int):
    """
    Kaskadning YURAGI. Rejalashtirilgan (Celery ETA/countdown) yoki foydalanuvchi
    "Davom etish" tugmasini bosgani sababli (bot handlerdan `.delay(...)`) chaqirilishi mumkin.
    """
    # ---- 1-FAZA: claim (qisqa tranzaksiya, tarmoq chaqiruvisiz) ----
    with transaction.atomic():
        cycle = SubscriptionRenewalCycle.objects.select_for_update().get(id=cycle_id)

        if cycle.is_terminal:
            logger.info("Cycle %s allaqachon yakunlangan (%s) — urinish tashlab ketildi.", cycle_id, cycle.status)
            return
        if cycle.attempt_number != expected_attempt_number:
            logger.info(
                "Cycle %s uchun eskirgan (stale) urinish (expected=%s, actual=%s) — tashlab ketildi.",
                cycle_id, expected_attempt_number, cycle.attempt_number,
            )
            return

        cycle.status = SubscriptionRenewalCycle.Status.IN_PROGRESS
        cycle.locked_at = timezone.now()
        cycle.attempt_number += 1
        cycle.save(update_fields=["status", "locked_at", "attempt_number"])
        current_attempt = cycle.attempt_number
        subscription = cycle.subscription

    # ---- 2-FAZA: haqiqiy to'lov (DB qulfisiz, sekin bo'lishi mumkin) ----
    order_id = f"renewal-{cycle_id}-{current_attempt}"

    # Ikki marta pul yechilishning oldini olish: agar OLDINGI urinish "error" bilan
    # tugagan bo'lsa-yu, o'sha safar receipt yaratilgan bo'lsa (ya'ni receipts.pay
    # javobi tarmoq xatosi bilan yo'qolgan bo'lishi mumkin bo'lsa) — yangi chek
    # yaratishdan OLDIN eski chekning HAQIQIY holatini Payme'dan so'raymiz.
    previous_attempt = (
        RenewalAttempt.objects.filter(cycle_id=cycle_id, attempt_number=current_attempt - 1, result="error")
        .exclude(payme_receipt_id__isnull=True).exclude(payme_receipt_id="")
        .first()
    )

    if previous_attempt is not None:
        client = PaymeClient()
        state = _resolve_previous_error_receipt(client, previous_attempt)
        if state == PaymeClient.RECEIPT_STATE_PAID:
            # Oldingi "xato" aslida MUVAFFAQIYATLI to'lov ekan — yangi so'rov yubormasdan
            # to'g'ridan-to'g'ri muvaffaqiyatli deb belgilaymiz.
            logger.info(
                "Cycle %s: oldingi chek (%s) aslida to'langan ekan (state=%s) — qayta pul "
                "yechilmadi, mavjud to'lov muvaffaqiyatli deb belgilandi.",
                cycle_id, previous_attempt.payme_receipt_id, state,
            )
            result = ChargeResult(
                outcome="success", transaction_id=previous_attempt.payme_receipt_id,
                receipt_id=previous_attempt.payme_receipt_id,
            )
            order_id = previous_attempt.payme_order_id
        elif state is None:
            # Holatni aniqlab bo'lmadi (Payme bilan yana aloqa yo'q) — xavfsizlik uchun bu
            # safar HECH QANDAY yangi to'lov qilinmaydi; keyingi urinishda yana tekshiriladi
            # (eski receipt_id shu yozuvga ham ko'chirib qo'yiladi — pastda).
            result = ChargeResult(
                outcome="error",
                error_reason="Oldingi to'lov holati tasdiqlanmadi (Payme bilan aloqa yo'q) — qayta tekshiriladi",
                receipt_id=previous_attempt.payme_receipt_id,
            )
        else:
            # state == RECEIPT_STATE_CANCELLED yoki boshqa yakuniy "to'lanmagan" holat —
            # pul yechilmagan, yangi chek bilan xavfsiz qayta urinish mumkin.
            result = _perform_charge(subscription, order_id)
    else:
        result = _perform_charge(subscription, order_id)

    # ---- 3-FAZA: natijani yozish va keyingi qadamni rejalashtirish ----
    with transaction.atomic():
        cycle = SubscriptionRenewalCycle.objects.select_for_update().get(id=cycle_id)
        RenewalAttempt.objects.get_or_create(
            cycle=cycle, attempt_number=current_attempt,
            defaults={
                "result": result.outcome, "error_reason": result.error_reason,
                "payme_order_id": order_id, "payme_receipt_id": result.receipt_id,
            },
        )
        cycle.last_result = result.outcome
        cycle.last_error_reason = result.error_reason

        if result.outcome == "success":
            _finalize_success(cycle, result.transaction_id)
            return

        # Agar bu urinish "eski chekning holati aniqlanmadi" sababli hech qanday yangi
        # to'lov qilmagan bo'lsa (receipts.check ham tarmoq xatosi bilan tugagan), avtomatik
        # bekor QILINMAYDI — aks holda pul aslida yechilgan bo'lsa ham obuna EXPIRED
        # bo'lib qolishi mumkin. Bunday holda cascade to'xtatilmaydi, keyingi urinishda
        # yana tekshiriladi, va bu holat log orqali qattiq (critical) belgilanadi —
        # amalda bu qatorga faqat Payme bilan bir necha marta ketma-ket aloqa uzilganda tushiladi.
        receipt_unresolved = result.outcome == "error" and bool(result.receipt_id) and previous_attempt is not None
        max_attempts = renewal_config.max_attempts()
        if current_attempt >= max_attempts and not receipt_unresolved:
            _finalize_cancel(cycle)
            return
        if receipt_unresolved and current_attempt >= max_attempts:
            logger.critical(
                "Cycle %s: max_attempts (%s) tugadi, lekin oldingi chek (%s) holati hali "
                "ham tasdiqlanmagan — QO'LDA tekshirish kerak. Obuna avtomatik bekor "
                "QILINMAYDI, cascade davom etadi.",
                cycle_id, max_attempts, result.receipt_id,
            )

        if result.outcome == "card_expired":
            cycle.status = SubscriptionRenewalCycle.Status.AWAITING_CARD_UPDATE
            wait_hours = renewal_config.retry_wait_hours(current_attempt)
            cycle.next_attempt_at = timezone.now() + timedelta(hours=wait_hours)
            cycle.save(update_fields=["status", "next_attempt_at", "last_result", "last_error_reason"])
            from bot.services.renewal_notifier import notify_card_expired
            notify_card_expired.delay(cycle.id)
        else:
            cycle.status = SubscriptionRenewalCycle.Status.AWAITING_USER
            wait_hours = renewal_config.retry_wait_hours(current_attempt)
            cycle.next_attempt_at = timezone.now() + timedelta(hours=wait_hours)
            cycle.save(update_fields=["status", "next_attempt_at", "last_result", "last_error_reason"])
            from bot.services.renewal_notifier import notify_payment_failed_stage
            notify_payment_failed_stage.delay(cycle.id, current_attempt)

        # Mijoz "Davom etish"ni bosmasa ham, belgilangan soatdan keyin tizim o'zi qayta urinadi.
        # `expected_attempt_number=current_attempt` — agar mijoz shu oraliqda tugmani bosib
        # ulgurgan bo'lsa, attempt_number allaqachon oshgan bo'ladi va bu rejalashtirilgan
        # chaqiruv 1-FAZAdagi tekshiruvda avtomatik tashlab ketiladi (18-bosqich kafolati).
        execute_renewal_attempt.apply_async(
            args=[cycle.id], kwargs={"expected_attempt_number": current_attempt},
            countdown=wait_hours * 3600,
        )


def _finalize_success(cycle: SubscriptionRenewalCycle, transaction_id: Optional[str]):
    cycle.status = SubscriptionRenewalCycle.Status.SUCCEEDED
    cycle.next_attempt_at = None
    cycle.save(update_fields=["status", "next_attempt_at", "last_result", "last_error_reason"])

    subscription = cycle.subscription
    plan = subscription.plan

    Payment.objects.create(
        subscription=subscription,
        amount=_effective_price_uzs(subscription),
        currency="UZS",
        provider=Subscription.Provider.PAYME,
        status=Payment.Status.SUCCESS,
        external_transaction_id=transaction_id,
        is_recurring_charge=True,
        paid_at=timezone.now(),
    )
    # Muddat asl jadvaldan (cycle.due_date) hisoblanadi — qayta urinishlar necha kun cho'zilishidan
    # qat'i nazar, keyingi to'lov sanasi siljib ketmasin degani.
    subscription.next_payment_date = cycle.due_date + relativedelta(months=plan.duration_months)
    subscription.status = Subscription.Status.ACTIVE
    subscription.save(update_fields=["next_payment_date", "status"])

    progress, _ = UserGiftProgress.objects.get_or_create(user=subscription.user)
    progress.register_successful_payment()

    from bot.services.renewal_notifier import notify_renewal_success
    notify_renewal_success.delay(cycle.id, transaction_id)


def _finalize_cancel(cycle: SubscriptionRenewalCycle):
    cycle.status = SubscriptionRenewalCycle.Status.CANCELLED
    cycle.next_attempt_at = None
    cycle.save(update_fields=["status", "next_attempt_at", "last_result", "last_error_reason"])

    subscription = cycle.subscription
    subscription.status = Subscription.Status.EXPIRED
    subscription.auto_renew = False
    subscription.save(update_fields=["status", "auto_renew"])

    progress, _ = UserGiftProgress.objects.get_or_create(user=subscription.user)
    progress.reset_streak()  # 9-bosqich: daraja "boshlovchi"ga tushadi, zinapoya boshidan boshlanadi

    from bot.services.renewal_notifier import notify_renewal_cancelled
    notify_renewal_cancelled.delay(cycle.id)

    from bot.services.channel_membership import kick_user_from_private_channel
    kick_user_from_private_channel(subscription.user.telegram_id)