"""
Faqat LOKAL DEV uchun: webhook o'rniga long polling orqali botni ishga tushiradi.
Prodda BUNI ishlatmang — u yerda `set_webhook` + `bot_webhook` (uvicorn/asgi) servisi ishlatiladi.
Polling kerak, chunki lokal Windows kompyuteringiz tashqi internetdan ochiq HTTPS manzilga
ega emas (webhook buni talab qiladi), polling esa hech qanday ochiq portsiz ishlaydi.

Ishlatish:
    python manage.py runbot_polling
"""

import asyncio

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Botni long polling rejimida ishga tushiradi (faqat lokal dev uchun)"

    def handle(self, *args, **options):
        from bot.loader import bot, dp

        self.stdout.write(self.style.SUCCESS("Bot polling rejimida ishga tushmoqda... (to'xtatish uchun Ctrl+C)"))
        asyncio.run(self._run(bot, dp))

    async def _run(self, bot, dp):
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
