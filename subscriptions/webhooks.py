import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from subscriptions.models import PendingCheckout, Payment
from subscriptions.services.subscription_service import activate_or_renew_subscription
from bot.services.notifier import notify_payment_success

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class PaymeWebhookView(View):
    """
    ESKIRGAN / ZAXIRA: bu Payme'ning HOSTED checkout oqimi uchun standart merchant webhooki
    (Payme bizga qo'ng'iroq qiladi). Loyihaning haqiqiy oqimi endi BUNDAY EMAS — biz o'z
    domenimizdagi (pay.turdievakademiyasi.uz) forma orqali karta ma'lumotini to'g'ridan-to'g'ri
    bizning backendimiz qabul qiladi va Payme Cards API bilan o'zi server-to-server gaplashadi:
    qarang `subscriptions/services/payment_form_service.py` va
    `api/payment_form_views.py`. Shu View faqat Payme tomonidan qo'shimcha nazorat
    (masalan GetStatement/CheckTransaction orqali solishtirish) kerak bo'lsa foydali bo'lishi
    mumkin bo'lgani uchun qoldirilgan, hozircha ishlatilmaydi.
    """

    def post(self, request, *args, **kwargs):
        self._check_auth(request)
        body = json.loads(request.body or "{}")
        method = body.get("method")
        params = body.get("params", {})

        handler = getattr(self, f"handle_{method}", None)
        if handler is None:
            return self._rpc_error(body.get("id"), -32601, "Method not found")
        return handler(body.get("id"), params)

    def _check_auth(self, request):
        # TODO(prod): Basic auth header ni PAYME_MERCHANT_ID/PAYME_SECRET_KEY bilan solishtirish
        pass

    def _rpc_result(self, request_id, result):
        return JsonResponse({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _rpc_error(self, request_id, code, message):
        return JsonResponse({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})

    def handle_CheckPerformTransaction(self, request_id, params):
        checkout_uuid = params.get("account", {}).get("order_id")
        exists = PendingCheckout.objects.filter(checkout_uuid=checkout_uuid, is_used=False).exists()
        if not exists:
            return self._rpc_error(request_id, -31050, "Order topilmadi yoki allaqachon to'langan")
        return self._rpc_result(request_id, {"allow": True})

    def handle_CreateTransaction(self, request_id, params):
        # TODO(prod): Payment(status=PENDING) yaratish, Payme transaction id bilan bog'lash
        return self._rpc_result(request_id, {"create_time": 0, "transaction": str(params.get("id")), "state": 1})

    def handle_PerformTransaction(self, request_id, params):
        checkout_uuid = params.get("account", {}).get("order_id")
        pending = PendingCheckout.objects.select_related("user", "plan", "renewal_cycle").get(
            checkout_uuid=checkout_uuid, is_used=False
        )

        card_token = params.get("card_token")  # recurring uchun saqlangan token, checkout oqimidan keladi
        masked_pan = params.get("card_number")

        if pending.purpose == "new_subscription":
            payment = activate_or_renew_subscription(
                pending_checkout=pending,
                external_transaction_id=str(params.get("id")),
                masked_pan=masked_pan,
                payme_card_token=card_token,
            )
            notify_payment_success.delay(payment.subscription.user_id, payment.id)

        elif pending.purpose == "card_change":
            # 15-bosqich: oddiy kartani almashtirish — hozir hech qanday summa yechilmaydi,
            # faqat karta tokeni saqlanadi (Payme card-verify oqimi 0 tiyinlik receipt bilan ham
            # amalga oshiriladi — TODO(prod): checkout linkda amount=0 va faqat cards.create+verify
            # chaqirilishini ta'minlash).
            from subscriptions.services.subscription_service import replace_primary_card
            replace_primary_card(pending.user, masked_pan, card_token)
            pending.is_used = True
            pending.save(update_fields=["is_used"])

        elif pending.purpose == "renewal_card_update":
            # 17-bosqich: to'lov kaskadi ichida karta yangilandi -> darhol yangi kartadan
            # ushbu billing davri uchun to'lovni qayta urinib ko'ramiz.
            from subscriptions.services.subscription_service import replace_primary_card
            from subscriptions.services.renewal_engine import execute_renewal_attempt

            replace_primary_card(pending.user, masked_pan, card_token)
            pending.is_used = True
            pending.save(update_fields=["is_used"])

            cycle = pending.renewal_cycle
            if cycle and not cycle.is_terminal:
                execute_renewal_attempt.delay(cycle.id, expected_attempt_number=cycle.attempt_number)

        return self._rpc_result(request_id, {"transaction": str(params.get("id")), "perform_time": 0, "state": 2})

    def handle_CancelTransaction(self, request_id, params):
        # TODO(prod): tegishli Payment(status=FAILED) qilish
        return self._rpc_result(request_id, {"transaction": str(params.get("id")), "cancel_time": 0, "state": -1})


@method_decorator(csrf_exempt, name="dispatch")
class TributeWebhookView(View):
    """
    Tribute webhooki: new_subscription / recurring_payment / cancelled_subscription eventlari.
    Header: X-Tribute-Signature — HMAC-SHA256(body, TRIBUTE_WEBHOOK_SECRET).
    """

    def post(self, request, *args, **kwargs):
        if not self._valid_signature(request):
            return JsonResponse({"detail": "invalid signature"}, status=403)

        event = json.loads(request.body or "{}")
        event_type = event.get("event_type")
        payload = event.get("payload", {})

        # DIQQAT (idempotentlik): Tribute (ko'pchilik webhook provayderlari kabi) bir xil
        # eventni bir necha marta yuborishi mumkin (bizning javobimiz sekin kelsa, tarmoq
        # uzilsa va h.k. — "kamida bir marta" kafolati, "aynan bir marta" emas). Shu sabab
        # `new_subscription` va `recurring_payment` ALOHIDA, bir-biriga aralashmaydigan
        # funksiyalarga ajratilgan: avvalgi kodda `new_subscription`ning qayta yuborilgan
        # nusxasi (pending.is_used=True bo'lib qolgani uchun) XATO ravishda "recurring_payment"
        # deb talqin qilinib, birinchi to'lovning o'ziga yana bir bor muddat qo'shib yuborar edi.
        if event_type == "new_subscription":
            self._handle_new_subscription(payload)
        elif event_type == "recurring_payment":
            self._handle_recurring_payment(payload)
        elif event_type == "cancelled_subscription":
            from subscriptions.models import Subscription
            Subscription.objects.filter(tribute_external_id=payload.get("subscription_id")).update(
                auto_renew=False, status=Subscription.Status.CANCELLED
            )

        return JsonResponse({"ok": True})

    @transaction.atomic
    def _handle_new_subscription(self, payload: dict):
        checkout_uuid = payload.get("label")  # bizning checkout_uuid shu yerda qaytadi
        pending = PendingCheckout.objects.select_related("user", "plan").filter(
            checkout_uuid=checkout_uuid,
        ).first()

        if pending is None:
            logger.warning("Tribute new_subscription: checkout_uuid=%s topilmadi.", checkout_uuid)
            return

        if pending.is_used:
            # Dublikat/qayta yuborilgan `new_subscription` — birinchi to'lov allaqachon
            # ishlangan. `_renew_from_recurring`ga hech qachon YO'NALTIRILMAYDI, aks holda
            # bitta haqiqiy to'lov ikkinchi marta "recurring" sifatida hisoblanib, obuna
            # muddati bekorga yana uzayib ketadi.
            logger.info(
                "Tribute new_subscription dublikat: checkout_uuid=%s allaqachon ishlangan — "
                "o'tkazib yuborildi.", checkout_uuid,
            )
            return

        payment = activate_or_renew_subscription(
            pending_checkout=pending,
            external_transaction_id=payload.get("subscription_id") or payload.get("payment_id"),
        )
        notify_payment_success.delay(payment.subscription.user_id, payment.id)

    def _handle_recurring_payment(self, payload: dict):
        from subscriptions.models import Subscription
        from subscriptions.services.subscription_service import _renew_from_recurring

        subscription = Subscription.objects.filter(
            tribute_external_id=payload.get("subscription_id")
        ).first()
        if subscription is None:
            logger.warning(
                "Tribute recurring_payment: subscription_id=%s bo'yicha obuna topilmadi.",
                payload.get("subscription_id"),
            )
            return

        # `_renew_from_recurring`ning o'zi `external_transaction_id` (payment_id) bo'yicha
        # idempotent — dublikat webhook kelsa, mavjud Payment qaytariladi, muddat qayta
        # uzaytirilmaydi.
        payment = _renew_from_recurring(subscription, payload.get("payment_id"))
        notify_payment_success.delay(subscription.user_id, payment.id)

    def _valid_signature(self, request) -> bool:
        signature = request.headers.get("X-Tribute-Signature", "")
        expected = hmac.new(settings.TRIBUTE_WEBHOOK_SECRET.encode(), request.body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
