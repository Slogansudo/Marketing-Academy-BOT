"""
pay.turdievakademiyasi.uz da ko'rsatilgan ikkita forma (rasm 1, 2) uchun backend mantiqi:

  - /payment?pay=<uuid>            -> PendingCheckout.purpose == "new_subscription"
  - /card-replacement?slug=<uuid>  -> PendingCheckout.purpose in ("card_change", "renewal_card_update")

Ikkala forma ham xuddi shu 2 bosqichli oqimdan o'tadi:
  1) POST .../process  {card_number, expire}  -> Payme cards.create + cards.get_verify_code
  2) POST .../verify    {code}                -> Payme cards.verify (+ kerak bo'lsa receipts.pay)

Xom karta raqami hech qachon saqlanmaydi — faqat shu funksiyalar orqali Payme'ga
forward qilinadi, DB ga esa faqat token/masklangan raqam yoziladi (PendingCheckout,
so'ng muvaffaqiyatli yakunlangach PaymentCard).
"""

from django.conf import settings
from django.utils import timezone

from subscriptions.models import PendingCheckout, Subscription
from subscriptions.services.payme_client import PaymeClient, PaymeError
from subscriptions.services.subscription_service import complete_pending_checkout

PAYMENT_PURPOSES = {"new_subscription"}
CARD_REPLACEMENT_PURPOSES = {"card_change", "renewal_card_update"}

MAX_VERIFY_ATTEMPTS = 5


class FormError(Exception):
    """View qatlami buni HTTP status kodiga map qiladi (status orqali)."""

    def __init__(self, message: str, status: int = 400, code: str = "error"):
        super().__init__(message)
        self.status = status
        self.code = code


def _get_pending(token, kind: str) -> PendingCheckout:
    allowed = PAYMENT_PURPOSES if kind == "payment" else CARD_REPLACEMENT_PURPOSES
    try:
        pending = PendingCheckout.objects.select_related("user", "plan", "renewal_cycle").get(checkout_uuid=token)
    except PendingCheckout.DoesNotExist:
        raise FormError("Havola topilmadi", status=404, code="not_found")

    if pending.purpose not in allowed:
        raise FormError("Havola noto'g'ri turdagi forma uchun", status=404, code="not_found")
    if pending.is_used:
        raise FormError("Bu havola orqali allaqachon amal bajarilgan", status=410, code="already_used")
    if pending.expires_at < timezone.now():
        raise FormError("Havola muddati tugagan. Botga qaytib qaytadan urinib ko'ring.", status=410, code="expired")
    return pending


def _amount_uzs(pending: PendingCheckout):
    if pending.purpose == "new_subscription":
        return pending.plan.price_uzs
    return None  # karta almashtirishda hozir hech narsa yechilmaydi


def _active_subscription_info(pending: PendingCheckout):
    """Agar mijozning ALLAQACHON aktiv obunasi bo'lsa, 'to'lov qilish' formasida karta
    so'rash o'rniga shuni bildirish kerak — chunki tizim next_payment_date kelganda
    bog'langan kartadan o'zi avtomatik pul yechadi, mijoz qayta to'lashi shart emas.
    Faqat yangi obuna (`new_subscription`) formasi uchun tegishli — karta almashtirish
    formasida aktiv obuna kutilgan holat, bu yerda ogohlantirish kerak emas.
    """
    if pending.purpose != "new_subscription":
        return None
    sub = (
        Subscription.objects.filter(user=pending.user, status=Subscription.Status.ACTIVE)
        .order_by("-next_payment_date")
        .first()
    )
    if not sub:
        return None
    return {
        "active_until": sub.next_payment_date,
        "auto_renew": sub.auto_renew,
    }


def get_form_context(token, kind: str) -> dict:
    pending = _get_pending(token, kind)
    seconds_left = max(0, int((pending.expires_at - timezone.now()).total_seconds()))
    active_info = _active_subscription_info(pending)
    return {
        "plan_title": pending.plan.title,
        "amount_uzs": _amount_uzs(pending),
        "amount_usd": pending.plan.price_usd if pending.purpose == "new_subscription" else None,
        "seconds_left": seconds_left,
        "purpose": pending.purpose,
        "duration_months": pending.plan.duration_months,
        "user_name": pending.user.full_name or "",
        "user_username": pending.user.username or "",
        "subscription_already_active": active_info is not None,
        "active_until": active_info["active_until"] if active_info else None,
        "active_auto_renew": active_info["auto_renew"] if active_info else None,
    }


def submit_card(token, kind: str, card_number: str, expire: str) -> dict:
    """1-bosqich: cards.create + get_verify_code. Muvaffaqiyatli bo'lsa SMS kod so'raladi."""
    pending = _get_pending(token, kind)

    # UI xabarini chetlab o'tib to'g'ridan-to'g'ri so'rov yuborilsa ham qayta to'lov
    # qilinmasligi uchun backend darajasida ham tekshiriladi (frontenddagi
    # "obunangiz aktiv" xabari — birinchi himoya qatlami, bu esa ikkinchisi).
    if _active_subscription_info(pending) is not None:
        raise FormError(
            "Sizning obunangiz allaqachon aktiv. To'lov qilish shart emas — tizim "
            "belgilangan sanada bog'langan kartangizdan avtomatik pul yechadi.",
            status=400, code="already_active",
        )

    client = PaymeClient()

    try:
        result = client.create_card(card_number=card_number, expire=expire)
        client.get_verify_code(result.token)
    except PaymeError as exc:
        raise FormError(str(exc), status=400, code=exc.reason_code)

    pending.pending_card_token = result.token
    pending.pending_masked_pan = result.masked_pan
    pending.verify_attempts = 0
    pending.save(update_fields=["pending_card_token", "pending_masked_pan", "verify_attempts"])

    return {"status": "verify_required", "masked_pan": result.masked_pan}


def submit_verify_code(token, kind: str, code: str) -> dict:
    """2-bosqich: cards.verify, so'ng (faqat 'payment' formasida) receipts.create+pay."""
    pending = _get_pending(token, kind)
    if not pending.pending_card_token:
        raise FormError("Avval karta ma'lumotlarini kiriting", status=400, code="card_not_submitted")
    if pending.verify_attempts >= MAX_VERIFY_ATTEMPTS:
        raise FormError("Urinishlar soni tugadi. Botga qaytib qaytadan boshlang.", status=429, code="too_many_attempts")

    client = PaymeClient()
    try:
        client.verify_card(pending.pending_card_token, code)
    except PaymeError as exc:
        pending.verify_attempts += 1
        pending.save(update_fields=["verify_attempts"])
        raise FormError(str(exc), status=400, code=exc.reason_code)

    external_transaction_id = pending.pending_card_token
    if pending.purpose == "new_subscription":
        if _active_subscription_info(pending) is not None:
            raise FormError(
                "Sizning obunangiz allaqachon aktiv. To'lov qilish shart emas — tizim "
                "belgilangan sanada bog'langan kartangizdan avtomatik pul yechadi.",
                status=400, code="already_active",
            )
        amount_tiyin = int(pending.plan.price_uzs * 100)
        order_id = f"checkout-{pending.checkout_uuid}"
        try:
            external_transaction_id = client.charge(pending.pending_card_token, amount_tiyin, order_id)
        except PaymeError as exc:
            raise FormError(str(exc), status=400, code=exc.reason_code)

    complete_pending_checkout(
        pending_checkout=pending,
        external_transaction_id=external_transaction_id,
        masked_pan=pending.pending_masked_pan,
        payme_card_token=pending.pending_card_token,
    )

    bot_username = settings.TELEGRAM_BOT_USERNAME
    return {"status": "success", "redirect_url": f"https://t.me/{bot_username}?start=paid"}
