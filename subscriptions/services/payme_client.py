"""
Payme "Cards" (recurring to'lov) integratsiyasi — Merchant API, JSON-RPC 2.0.
Hujjat: https://developer.help.paycom.uz/metody-cards/

Bu yerdagi oqim Payme'ning HOSTED checkout'i (checkout.payme.uz) EMAS — bizning
o'z domenimizdagi (pay.turdievakademiyasi.uz) forma orqali karta raqami/muddati
to'g'ridan-to'g'ri BIZNING backendimizga POST qilinadi, so'ng biz shu 5 metod
orqali Payme bilan serverdan-serverga gaplashamiz:

  1. cards.create(number, expire)                -> {"card": {"token": "...", "number": "561468******7403"}}
  2. cards.get_verify_code(token)                 -> Payme mijoz raqamiga SMS kod yuboradi
  3. cards.verify(token, code)                    -> karta tasdiqlanadi (endi undan pul yechish mumkin)
  4. receipts.create(amount, account={"order_id": ...}) -> {"receipt": {"_id": "..."}}
  5. receipts.pay(receipt_id, token)              -> to'lov amalga oshadi (recurring uchun ham shu)
  6. receipts.check(receipt_id)                   -> {"state": N} — chekning HAQIQIY holati
     (4 = to'langan, 50 = bekor qilingan). receipts.pay javobi tarmoq xatosi bilan
     yo'qolgan hollarda — retrydan oldin shu bilan tekshirib chiqiladi (pastga qarang).

MUHIM (ikki marta pul yechilishning oldini olish): agar receipts.pay chaqiruvi
vaqtida Payme pulni allaqachon yechib ulgursa-yu, javob esa tarmoq uzilishi/timeout
sabab bizga yetib kelmasa — receipts.create/pay o'z-o'zidan bu holatni "xato" deb
belgilaydi. Payme'ning order_id-asosidagi dublikat himoyasi bunda yordam bermaydi,
chunki retry'da order_id ham o'zgaradi (cycle_id+attempt_number asosida noyob).
Shu sabab: PaymeError endi yaratilgan receipt_id'ni o'zida olib yuradi
(PaymeError.receipt_id), chaqiruvchi (renewal_engine) buni saqlab qo'yadi va
KEYINGI urinishdan OLDIN receipts.check bilan haqiqiy holatni tekshiradi — agar
u aslida to'langan bo'lib chiqsa, yangi chek yaratilmaydi/pul qayta yechilmaydi.

MUHIM (xavfsizlik): karta raqami/muddati hech qachon bizning bazamizga yozilmaydi —
faqat shu klass orqali Payme'ga forward qilinadi va javobdagi TOKEN + masklangan
raqam saqlanadi (PendingCheckout.pending_card_token / PaymentCard.payme_card_token).
Shu tufayli PCI-DSS doirasi minimal (SAQ A-EP ga yaqin) bo'ladi — lekin baribir forma
faqat HTTPS orqali, karta raqami hech qachon log qilinmasdan ishlashi shart.
"""

import logging
import uuid
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_INSUFFICIENT_FUNDS_CODES = {-31001, -31099}
_CARD_EXPIRED_CODES = {-31003, -31084}
_CARD_INVALID_CODES = {-31300, -31301, -31302}


class PaymeError(Exception):
    def __init__(
        self,
        message: str,
        reason_code: str = "error",
        raw_code: int | None = None,
        receipt_id: str | None = None,
    ):
        super().__init__(message)
        self.reason_code = reason_code
        self.raw_code = raw_code
        # Agar bu xato receipts.create MUVAFFAQIYATLI bo'lgandan keyin (masalan
        # receipts.pay paytida tarmoq uzilib) yuz bergan bo'lsa, chaqiruvchi shu
        # receipt_id'ni saqlab qo'yishi kerak — keyingi urinishdan oldin uning
        # HAQIQIY holatini receipts.check bilan tekshirish uchun (ikki marta pul
        # yechilishining oldini olish).
        self.receipt_id = receipt_id


@dataclass
class CardCreateResult:
    token: str
    masked_pan: str
    recurrent: bool = True


class PaymeClient:
    # receipts.check javobidagi `state` kodlari (to'liq ro'yxat: Payme hujjati
    # "Состояния чека"). Bizga faqat shu ikkitasi — YAKUNIY holatlar — kerak.
    RECEIPT_STATE_PAID = 4
    RECEIPT_STATE_CANCELLED = 50

    def __init__(self):
        self.merchant_id = settings.PAYME_MERCHANT_ID
        self.secret_key = settings.PAYME_SECRET_KEY
        self.api_url = settings.PAYME_API_URL

    def build_payment_form_url(self, checkout_uuid: uuid.UUID, kind: str = "payment") -> str:
        base = settings.PAYMENT_BASE_URL.rstrip("/")
        if kind == "card-replacement":
            return f"{base}/card-replacement?slug={checkout_uuid}"
        return f"{base}/payment?pay={checkout_uuid}"

    def _call(self, method: str, params: dict) -> dict:
        import base64

        auth = base64.b64encode(f"{self.merchant_id}:{self.secret_key}".encode()).decode()
        try:
            resp = requests.post(
                self.api_url,
                json={"id": 0, "method": method, "params": params},
                headers={"X-Auth": f"{self.merchant_id}:{self.secret_key}", "Authorization": f"Basic {auth}"},
                timeout=15,
            )
            body = resp.json()
        except requests.RequestException as exc:
            logger.exception("Payme API so'rovida tarmoq xatoligi: %s", method)
            raise PaymeError(f"Payme bilan aloqa xatosi: {exc}", reason_code="error") from exc

        if "error" in body and body["error"]:
            err = body["error"]
            code = err.get("code")
            message = err.get("message", {})
            text = message.get("uz") or message.get("ru") or message.get("en") or str(message)
            if code in _INSUFFICIENT_FUNDS_CODES:
                raise PaymeError(text, reason_code="insufficient_funds", raw_code=code)
            if code in _CARD_EXPIRED_CODES:
                raise PaymeError(text, reason_code="card_expired", raw_code=code)
            if code in _CARD_INVALID_CODES:
                raise PaymeError(text, reason_code="card_invalid", raw_code=code)
            raise PaymeError(text, reason_code="error", raw_code=code)

        return body.get("result", {})

    def create_card(self, card_number: str, expire: str) -> CardCreateResult:
        result = self._call("cards.create", {"card": {"number": card_number, "expire": expire}, "save": True})
        card = result.get("card", {})
        return CardCreateResult(token=card["token"], masked_pan=card["number"], recurrent=card.get("recurrent", False))

    def get_verify_code(self, token: str) -> None:
        self._call("cards.get_verify_code", {"token": token})

    def verify_card(self, token: str, sms_code: str) -> bool:
        result = self._call("cards.verify", {"token": token, "code": sms_code})
        return bool(result.get("card", {}).get("recurrent"))

    def create_receipt(self, amount_tiyin: int, order_id: str) -> str:
        result = self._call("receipts.create", {"amount": amount_tiyin, "account": {"order_id": order_id}})
        return result["receipt"]["_id"]

    def pay_receipt(self, receipt_id: str, card_token: str) -> str:
        result = self._call("receipts.pay", {"id": receipt_id, "token": card_token})
        return result["receipt"]["_id"]

    def check_receipt(self, receipt_id: str) -> int:
        """receipts.check — chekning Payme tomonidagi HAQIQIY holatini so'raydi.
        Bizning bazamizdagi holatga emas, aynan shu javobga tayanish kerak: agar
        oldingi receipts.pay chaqiruvi tarmoq xatosi bilan tugagan bo'lsa ham,
        pul aslida allaqachon yechilgan bo'lishi mumkin (state == RECEIPT_STATE_PAID).
        """
        result = self._call("receipts.check", {"id": receipt_id})
        return result["state"]

    def charge(self, card_token: str, amount_tiyin: int, order_id: str, existing_receipt_id: str | None = None) -> str:
        """
        `existing_receipt_id` berilsa, receipts.create QAYTA chaqirilmaydi — bevosita
        o'sha eski chek to'lanadi (masalan receipts.check orqali "hali to'lanmagan"
        deb tasdiqlangan chekni qayta urinish uchun).

        Agar receipts.create yoki receipts.pay xato bilan tugasa, yaratilgan
        receipt_id (bo'lsa) PaymeError.receipt_id orqali chaqiruvchiga uzatiladi —
        shu orqali chaqiruvchi keyingi urinishdan oldin uning holatini
        receipts.check bilan tekshirib chiqishi mumkin bo'ladi.
        """
        receipt_id = existing_receipt_id or self.create_receipt(amount_tiyin, order_id)
        try:
            return self.pay_receipt(receipt_id, card_token)
        except PaymeError as exc:
            exc.receipt_id = receipt_id
            raise
