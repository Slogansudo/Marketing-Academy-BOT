import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.conf import settings
from rest_framework import authentication, exceptions

from users.models import TelegramUser

INIT_DATA_MAX_AGE_SECONDS = 3600 * 6  # 6 soatdan eski initData qabul qilinmaydi


class TelegramInitDataAuthentication(authentication.BaseAuthentication):
    """
    Mini app (React) har bir so'rovda `Authorization: TgWebApp <initData>` headerini yuboradi.
    initData Telegram WebApp SDK tomonidan avtomatik generatsiya qilinadi va bizga mijozning
    telegram_id sini xavfsiz (hash orqali tekshirilgan) tarzda beradi — shu sabab alohida login/parol
    kerak emas (bot orqaligina mini appga kirish mumkin bo'lishining texnik sababi ham shu).
    """

    keyword = "TgWebApp"

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith(self.keyword):
            return None

        init_data = header[len(self.keyword):].strip()
        data = self._validate_init_data(init_data)

        user_payload = json.loads(data.get("user", "{}"))
        telegram_id = user_payload.get("id")
        if not telegram_id:
            raise exceptions.AuthenticationFailed("initData ichida foydalanuvchi topilmadi")

        try:
            user = TelegramUser.objects.get(telegram_id=telegram_id)
        except TelegramUser.DoesNotExist:
            raise exceptions.AuthenticationFailed("Foydalanuvchi ro'yxatdan o'tmagan (avval botda /start bosilishi kerak)")

        return (user, None)

    def _validate_init_data(self, init_data: str) -> dict:
        if not init_data:
            raise exceptions.AuthenticationFailed("initData bo'sh")

        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            raise exceptions.AuthenticationFailed("initData hash mavjud emas")

        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > INIT_DATA_MAX_AGE_SECONDS:
            raise exceptions.AuthenticationFailed("initData muddati o'tgan")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            raise exceptions.AuthenticationFailed("initData imzosi noto'g'ri")

        return parsed
