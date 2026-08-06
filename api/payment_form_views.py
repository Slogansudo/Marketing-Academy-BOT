"""
pay.turdievakademiyasi.uz frontendi (alohida statik/React sahifa) shu endpointlarga
so'rov yuboradi. Bular Telegram mini app EMAS — oddiy brauzer orqali ochiladi, shuning
uchun standart `TelegramInitDataAuthentication` bu yerga mos emas: `authentication_classes = []`,
`permission_classes = [AllowAny]`. O'rniga xavfsizlik `PendingCheckout.checkout_uuid`
(taxmin qilib bo'lmaydigan UUID4, 15 daqiqalik TTL, bir martalik) orqali ta'minlanadi.
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from subscriptions.services.payment_form_service import (
    FormError, get_form_context, submit_card, submit_verify_code,
)


class BasePaymentFormView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    kind = None  # "payment" | "card-replacement" — subklasslarda belgilanadi

    def _error(self, exc: FormError):
        return Response({"detail": str(exc), "code": exc.code}, status=exc.status)


class PaymentFormDetailView(BasePaymentFormView):
    kind = "payment"

    def get(self, request, token):
        try:
            return Response(get_form_context(token, self.kind))
        except FormError as exc:
            return self._error(exc)


class PaymentFormProcessView(BasePaymentFormView):
    kind = "payment"

    def post(self, request, token):
        card_number = (request.data.get("card_number") or "").replace(" ", "")
        expire = (request.data.get("expire") or "").replace("/", "").replace(" ", "")
        if not card_number.isdigit() or len(card_number) != 16:
            return Response({"detail": "Karta raqami noto'g'ri", "code": "invalid_card"}, status=400)
        if not expire.isdigit() or len(expire) != 4:
            return Response({"detail": "Muddat noto'g'ri (MM/YY)", "code": "invalid_expire"}, status=400)
        try:
            return Response(submit_card(token, self.kind, card_number, expire))
        except FormError as exc:
            return self._error(exc)


class PaymentFormVerifyView(BasePaymentFormView):
    kind = "payment"

    def post(self, request, token):
        code = (request.data.get("code") or "").strip()
        if not code:
            return Response({"detail": "Tasdiqlash kodini kiriting", "code": "invalid_code"}, status=400)
        try:
            return Response(submit_verify_code(token, self.kind, code))
        except FormError as exc:
            return self._error(exc)


class CardReplacementFormDetailView(PaymentFormDetailView):
    kind = "card-replacement"


class CardReplacementFormProcessView(PaymentFormProcessView):
    kind = "card-replacement"


class CardReplacementFormVerifyView(PaymentFormVerifyView):
    kind = "card-replacement"
