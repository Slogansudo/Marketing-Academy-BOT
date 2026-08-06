import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from aiogram.types import Update

from bot.loader import bot, dp


@csrf_exempt
async def telegram_webhook(request, secret: str):
    """
    Telegram `setWebhook` shu manzilga sozlanadi: /bot/webhook/<TELEGRAM_WEBHOOK_SECRET>/
    Secret token URL ichida bo'lgani uchun begona so'rovlar rad etiladi.
    """
    if secret != settings.TELEGRAM_WEBHOOK_SECRET:
        return HttpResponseForbidden()

    if request.method != "POST":
        return HttpResponse(status=405)

    data = json.loads(request.body)
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return HttpResponse(status=200)
