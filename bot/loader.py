from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from django.conf import settings

bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# FSM holati (ism/telefon so'rash bosqichi, tarif/to'lov usuli tanlash bosqichi va h.k.)
# Redisda saqlanadi — Celery workerlar va Django webhook view bir xil holatni ko'radi.
storage = RedisStorage.from_url(settings.CELERY_BROKER_URL)

dp = Dispatcher(storage=storage)


def register_all_handlers():
    from bot.handlers import registration, subscription, menu, subscription_status, mini_app_gift, renewal

    dp.include_router(registration.router)
    dp.include_router(subscription.router)
    dp.include_router(menu.router)
    dp.include_router(subscription_status.router)
    dp.include_router(mini_app_gift.router)
    dp.include_router(renewal.router)


register_all_handlers()
