"""
Eskiz.uz SMS shlyuzi integratsiyasi (https://eskiz.uz/api-berish).
Oqim: /auth/login (token olish, ~30 kunga amal qiladi, keshlanadi) -> /message/sms/send.

17-bosqich: to'lov yechilishidan 1 kun oldin SMS yuboriladi. Bu klass shu SMS'ni jo'natish
uchun yupqa wrapper; token olish/keshlash logikasi keltirilgan, HTTP chaqiruv joyi esa
haqiqiy Eskiz akkaunt ma'lumotlari ulanganda to'ldiriladi (TODO(prod)).
"""

import requests
from django.conf import settings
from django.core.cache import cache

ESKIZ_BASE_URL = "https://notify.eskiz.uz/api"
TOKEN_CACHE_KEY = "eskiz_sms_token"


class EskizSMSError(Exception):
    pass


class EskizClient:
    def __init__(self):
        self.email = getattr(settings, "ESKIZ_EMAIL", "")
        self.password = getattr(settings, "ESKIZ_PASSWORD", "")

    def _get_token(self) -> str:
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
        # TODO(prod): POST {ESKIZ_BASE_URL}/auth/login {email, password} -> {"data": {"token": "..."}}
        raise EskizSMSError("Eskiz auth integratsiyasi hali ulanmagan")

    def send_sms(self, phone_number: str, message: str) -> None:
        """
        17-bosqich SMS matni: 'Yaxshimisiz? Davronbek Turdiev Akademiyasi uchun oylik
        obunangiz ertaga tugaydi. Obunani uzaytirishda muammo bo'lmasligi uchun kartangiz
        balansini tekshiring' — matn statik (cms.bot_texts, slug='renewal_reminder_1d_sms')
        orqali kodda saqlanadi, shu yerga tayyor holda keladi.
        """
        token = self._get_token()
        # TODO(prod): POST {ESKIZ_BASE_URL}/message/sms/send
        #   headers={"Authorization": f"Bearer {token}"}
        #   data={"mobile_phone": phone_number.lstrip("+"), "message": message, "from": "4546"}
        raise NotImplementedError("Eskiz SMS yuborish HTTP integratsiyasi ulanishi kerak")
