import time

from celery import shared_task
from django.utils import timezone

from users.models import TelegramUser
from subscriptions.models import Subscription
from broadcast.models import Broadcast, BroadcastRecipient
from bot.services.notifier import _send_message, _send_photo, _send_video, _send_video_note, _url_button

SEND_DELAY_SECONDS = 0.05  # Telegram rate-limit (~30 xabar/sekund) ga tushmaslik uchun


def _resolve_recipients(broadcast: Broadcast):
    if broadcast.target_type == Broadcast.TargetType.ALL:
        return TelegramUser.objects.filter(is_blocked_bot=False)
    if broadcast.target_type == Broadcast.TargetType.ACTIVE_SUBSCRIBERS:
        user_ids = Subscription.objects.filter(status=Subscription.Status.ACTIVE).values_list("user_id", flat=True)
        return TelegramUser.objects.filter(id__in=user_ids, is_blocked_bot=False)
    if broadcast.target_type == Broadcast.TargetType.EXPIRED_SUBSCRIBERS:
        user_ids = Subscription.objects.filter(status=Subscription.Status.EXPIRED).values_list("user_id", flat=True)
        return TelegramUser.objects.filter(id__in=user_ids, is_blocked_bot=False)
    if broadcast.target_type == Broadcast.TargetType.SPECIFIC_PLAN:
        user_ids = Subscription.objects.filter(plan=broadcast.target_plan).values_list("user_id", flat=True)
        return TelegramUser.objects.filter(id__in=user_ids, is_blocked_bot=False)
    if broadcast.target_type == Broadcast.TargetType.CUSTOM_LIST:
        return broadcast.custom_users.filter(is_blocked_bot=False)
    return TelegramUser.objects.none()


@shared_task
def dispatch_scheduled_broadcast(broadcast_id: int, expected_scheduled_at: str | None = None):
    """
    Celery `eta` bilan rejalashtirilgan vaqtda ishga tushadi.

    Ikki xil holatda yuborishning oldi olinadi:
    - Admin e'lonni o'chirgan yoki holatini SCHEDULED'dan boshqasiga o'zgartirgan bo'lsa
      (masalan qo'lda "Yuborish" bosgan yoki qoralamaga qaytargan).
    - Admin `scheduled_at` vaqtini QAYTA o'zgartirgan bo'lsa — bu holda eski (endi eskirgan)
      eta bilan navbatga qo'yilgan ushbu vazifa `expected_scheduled_at` mos kelmagani uchun
      hech narsa qilmay chiqib ketadi, yangi vaqt uchun esa alohida vazifa navbatga qo'yilgan bo'ladi.
    """
    try:
        broadcast = Broadcast.objects.get(id=broadcast_id)
    except Broadcast.DoesNotExist:
        return
    if broadcast.status != Broadcast.Status.SCHEDULED:
        return
    if expected_scheduled_at:
        from django.utils.dateparse import parse_datetime
        expected_dt = parse_datetime(expected_scheduled_at)
        # Solishtirish datetime OBYEKTLARI orqali qilinishi shart, matn (isoformat) orqali emas —
        # bir xil moment turli timezone bilan turlicha string bo'lib chiqishi mumkin
        # (masalan "+05:00" va keyin DB'dan qaytganda "+00:00"), shu sabab avvalgi versiyada
        # bir xil vaqt "o'zgartirilgan" deb noto'g'ri aniqlanib, e'lon umuman yuborilmay qolgan edi.
        if not broadcast.scheduled_at or (expected_dt and broadcast.scheduled_at != expected_dt):
            return
    broadcast.status = Broadcast.Status.QUEUED
    broadcast.save(update_fields=["status"])
    send_broadcast_task.delay(broadcast.id)


@shared_task
def send_broadcast_task(broadcast_id: int):
    """16-bosqich: admin global yoki tanlab (segment) yuborgan e'lonni haqiqatda jo'natadi."""
    broadcast = Broadcast.objects.get(id=broadcast_id)
    broadcast.status = Broadcast.Status.SENDING
    recipients = list(_resolve_recipients(broadcast))
    broadcast.total_recipients = len(recipients)
    broadcast.save(update_fields=["status", "total_recipients"])

    reply_markup = (
        _url_button(broadcast.button_text, broadcast.button_url)
        if broadcast.button_text and broadcast.button_url
        else None
    )

    for user in recipients:
        recipient, _ = BroadcastRecipient.objects.get_or_create(broadcast=broadcast, user=user)
        if recipient.is_sent:
            continue
        try:
            if broadcast.video and broadcast.is_video_note:
                # Dumaloq video xabar (video note) — Telegram matnni video note bilan birga
                # yuborishni qo'llab-quvvatlamaydi, shuning uchun avval video, keyin matn/tugma.
                # FAYL_ID KESHLASH: birinchi yuborishda haqiqiy fayl yuklanadi, Telegram qaytargan
                # file_id saqlanadi — keyingi HAR BIR qabul qiluvchiga endi fayl umuman qayta
                # yuklanmaydi, faqat shu ID orqali (deyarli bir zumda) yuboriladi.
                source = broadcast.video_file_id or broadcast.video
                file_id = _send_video_note(user.telegram_id, source)
                if file_id and not broadcast.video_file_id:
                    broadcast.video_file_id = file_id
                    broadcast.save(update_fields=["video_file_id"])
                if broadcast.text or reply_markup:
                    _send_message(user.telegram_id, broadcast.text, reply_markup=reply_markup)
            elif broadcast.video:
                source = broadcast.video_file_id or broadcast.video
                file_id = _send_video(user.telegram_id, source, broadcast.text, reply_markup=reply_markup)
                if file_id and not broadcast.video_file_id:
                    broadcast.video_file_id = file_id
                    broadcast.save(update_fields=["video_file_id"])
            elif broadcast.image:
                source = broadcast.image_file_id or broadcast.image
                file_id = _send_photo(user.telegram_id, source, broadcast.text, reply_markup=reply_markup)
                if file_id and not broadcast.image_file_id:
                    broadcast.image_file_id = file_id
                    broadcast.save(update_fields=["image_file_id"])
            else:
                _send_message(user.telegram_id, broadcast.text, reply_markup=reply_markup)
            recipient.is_sent = True
            recipient.sent_at = timezone.now()
            recipient.save(update_fields=["is_sent", "sent_at"])
            broadcast.sent_count += 1
        except Exception as exc:  # noqa: BLE001
            recipient.error = str(exc)[:255]
            recipient.save(update_fields=["error"])
            broadcast.failed_count += 1
            if "blocked" in str(exc).lower() or "403" in str(exc):
                user.is_blocked_bot = True
                user.save(update_fields=["is_blocked_bot"])
        time.sleep(SEND_DELAY_SECONDS)

    broadcast.status = Broadcast.Status.SENT
    broadcast.sent_at = timezone.now()
    broadcast.save(update_fields=["status", "sent_at", "sent_count", "failed_count"])
    