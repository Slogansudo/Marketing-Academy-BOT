from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

from subscriptions.models import Subscription, PendingCheckout, PaymentReminderLog
from subscriptions import renewal_config

# ---------------------------------------------------------------------------
# 17-bosqich: to'lovdan oldingi eslatmalar (3/2/1 kun, subscriptions/renewal_config.py'da statik)
# ---------------------------------------------------------------------------


@shared_task
def send_renewal_reminders():
    """
    Har doim aniq 3 ta bosqich (1/2/3) uchun — har biriga mos "necha kun oldin"
    qiymati `renewal_config.reminder_stage_days(stage)` orqali (admin panelda
    tahrirlanadigan) olinadi. Botga esa QIYMAT emas, BOSQICH raqami yuboriladi —
    shu bilan matn slug'i hech qachon "topilmadi" bo'lib qolmaydi (qarang:
    `renewal_config.py` docstringi).
    PaymentReminderLog orqali bir kunda faqat bir marta yuborilishi kafolatlanadi (task
    soatiga bir necha marta ishga tushsa ham qayta yubormaydi).
    """
    from bot.services.renewal_notifier import notify_renewal_reminder, notify_renewal_reminder_sms

    today = date.today()
    sms_stage = renewal_config.sms_on_stage()

    for stage in renewal_config.all_reminder_stages():
        days_before = renewal_config.reminder_stage_days(stage)
        target_date = today + timedelta(days=days_before)
        subscriptions = Subscription.objects.filter(
            provider=Subscription.Provider.PAYME,
            status=Subscription.Status.ACTIVE,
            auto_renew=True,
            next_payment_date=target_date,
        )
        for subscription in subscriptions:
            _, created = PaymentReminderLog.objects.get_or_create(
                subscription=subscription,
                due_date=target_date,
                reminder_type=PaymentReminderLog.ReminderType.DAYS_BEFORE,
                days_before=days_before,
            )
            if created:
                notify_renewal_reminder.delay(subscription.id, stage)

            if stage == sms_stage and sms_stage > 0:
                _, sms_created = PaymentReminderLog.objects.get_or_create(
                    subscription=subscription,
                    due_date=target_date,
                    reminder_type=PaymentReminderLog.ReminderType.SMS_DAY_BEFORE,
                    days_before=days_before,
                )
                if sms_created:
                    notify_renewal_reminder_sms.delay(subscription.id)


# ---------------------------------------------------------------------------
# 17-18-bosqich: to'lov kuni kelganda kaskadni ishga tushirish
# ---------------------------------------------------------------------------


@shared_task
def create_due_renewal_cycles():
    from subscriptions.services.renewal_engine import create_due_cycles

    return create_due_cycles()


@shared_task
def cleanup_expired_pending_checkouts():
    """4-bosqich: to'lov sahifasidagi 15 daqiqalik taymer (2, 7-rasm) tugagan checkoutlarni tozalaydi."""
    PendingCheckout.objects.filter(is_used=False, expires_at__lt=timezone.now()).delete()
