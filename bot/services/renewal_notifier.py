# JOYLASHTIRISH MANZILI: ACADEMY_BACK/bot/services/renewal_notifier.py

"""
Avto-to'lov bildirishnomalari — 2-avlod DINAMIK kaskad.

ESKI: har bir urinish/hodisa qattiq bitta slug'ga bog'langan edi (FAIL_STAGE_SLUGS).
YANGI: har bir hodisa/urinish uchun `cms.services.send_cascade_stage_raw` chaqiriladi —
u admin konstruktorda (`BotMessageTemplate`, group='renewal_fail_cascade') o'sha aniq
`trigger_event`/`attempt_number`ga FAOL qilib biriktirilgan BARCHA xabarlarni (CORE va
CUSTOM, pozitsiya bo'yicha ketma-ket) yuboradi. Admin bitta urinishni butunlay
"jim" qoldirishi (hech qanday xabar qo'ymasligi) yoki bitta urinishga bir nechta
xabar (masalan matn + rasm) qo'shishi — ikkalasi ham qo'llab-quvvatlanadi.

`renewal_reminders` guruhi (to'lovdan OLDINGI 3/2/1-kun eslatmalari) alohida —
bular kalendar-sanaga bog'langan uchta mustaqil trigger, shuning uchun
`send_group_step_raw` orqali (guruh ichidagi pozitsiyaga qarab, shu slug'dan
KEYIN qo'shilgan CUSTOM xabarlar bilan birga) yuboriladi.
"""

from celery import shared_task

from cms.services import send_group_step_raw, send_cascade_stage_raw
from subscriptions.models import SubscriptionRenewalCycle, Subscription


def _inline_button(text: str, callback_data: str) -> dict:
    return {"inline_keyboard": [[{"text": text, "callback_data": callback_data}]]}


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_renewal_reminder(self, subscription_id: int, stage: int):
    """
    17-bosqich: to'lovdan oldingi eslatmalar (1/2/3-bosqich).

    E'TIBOR: bu yerda BOSQICH raqami (1/2/3) bo'yicha qidiriladi, kun soni bo'yicha
    emas — shunda admin panelda "necha kun oldin" qiymati o'zgartirilsa ham (masalan
    3 kun -> 5 kun), mos matn slug'i hech qachon topilmay qolmaydi.
    """
    slug_map = {1: "renewal_reminder_3d", 2: "renewal_reminder_2d", 3: "renewal_reminder_1d"}
    try:
        subscription = Subscription.objects.select_related("user", "plan").get(id=subscription_id)
        slug = slug_map.get(stage, "renewal_reminder_1d")
        context = {
            "tarif_name": subscription.plan.title,
            "expires_at": subscription.next_payment_date.strftime("%d.%m.%Y"),
        }
        send_group_step_raw("renewal_reminders", slug, subscription.user.telegram_id, context)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_renewal_reminder_sms(self, subscription_id: int):
    """
    17-bosqich: to'lovdan 1 kun oldin Eskiz orqali SMS. Bu voronka konstruktoridagi
    "ketma-ket xabarlar" tushunchasidan TASHQARIDA qoladi (talabga ko'ra: "Eskiz sms
    matniga tegib o'tirmasin, faqat qachon yuborishni o'zi hal qilsin") — matn hamon
    `renewal_reminder_1d_sms` slug'idan (admin panelda tahrirlanadigan, bazadan)
    olinadi, lekin bu yagona SMS xabar sifatida qoladi, CUSTOM xabar zanjiriga
    ulanmaydi.
    """
    from subscriptions.services.eskiz_client import EskizClient, EskizSMSError
    from cms.bot_texts import get_bot_text

    try:
        subscription = Subscription.objects.select_related("user", "plan").get(id=subscription_id)
        if not subscription.user.phone_number:
            return
        text = get_bot_text("renewal_reminder_1d_sms")
        EskizClient().send_sms(subscription.user.phone_number, text)
    except EskizSMSError:
        # SMS integratsiyasi hali ulanmagan dev muhitda jim o'tkazib yuboriladi
        pass
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_payment_failed_stage(self, cycle_id: int, attempt_number: int):
    """
    Avto-to'lov muvaffaqiyatsiz bo'lganda — aynan shu `attempt_number` uchun admin
    konstruktorda belgilangan xabarlar ketma-ket yuboriladi ('Davom etish' tugmasi
    faqat OXIRGI xabarga qo'yiladi). Admin bu urinishga xabar qo'ymagan bo'lsa,
    hech narsa yuborilmaydi — bu KUTILGAN xulq-atvor (talabga qarang: "2-urinishda
    yubormasdan, 3-urinishda yuboriladigan xabarni qo'sha olsin").
    """
    try:
        cycle = SubscriptionRenewalCycle.objects.select_related("subscription__user", "subscription__plan").get(id=cycle_id)
        subscription = cycle.subscription
        context = {
            "tarif_name": subscription.plan.title,
            "amount": f"{subscription.plan.price_uzs:,.0f}",
            "error_reason": cycle.last_error_reason or "Kartada mablag' yetarli emas",
        }
        send_cascade_stage_raw(
            subscription.user.telegram_id,
            trigger_event="attempt",
            attempt_number=attempt_number,
            context=context,
            reply_markup=_inline_button("Davom etish", f"renewal_continue:{cycle_id}"),
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_card_expired(self, cycle_id: int):
    try:
        cycle = SubscriptionRenewalCycle.objects.select_related("subscription__user", "subscription__plan").get(id=cycle_id)
        subscription = cycle.subscription
        send_cascade_stage_raw(
            subscription.user.telegram_id,
            trigger_event="card_expired",
            reply_markup=_inline_button("Kartani almashtirish", f"renewal_change_card:{cycle_id}"),
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_renewal_success(self, cycle_id: int, transaction_id: str | None):
    try:
        cycle = SubscriptionRenewalCycle.objects.select_related("subscription__user", "subscription__plan").get(id=cycle_id)
        subscription = cycle.subscription
        context = {
            "tarif_name": subscription.plan.title,
            "amount": f"{subscription.plan.price_uzs:,.0f}",
            "expires_at": subscription.next_payment_date.strftime("%d.%m.%Y"),
        }
        send_cascade_stage_raw(subscription.user.telegram_id, trigger_event="success", context=context)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def notify_renewal_cancelled(self, cycle_id: int):
    try:
        cycle = SubscriptionRenewalCycle.objects.select_related("subscription__user").get(id=cycle_id)
        subscription = cycle.subscription
        send_cascade_stage_raw(
            subscription.user.telegram_id,
            trigger_event="cancelled",
            reply_markup=_inline_button("Obuna tiklash", "renewal_reactivate"),
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)