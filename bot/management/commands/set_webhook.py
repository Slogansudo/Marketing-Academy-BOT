import asyncio
from django.conf import settings
from django.core.management.base import BaseCommand
from bot.loader import bot


class Command(BaseCommand):
    help = "Telegram webhookni serverga sozlaydi (Telegram -> bizning /bot/webhook/<secret>/ manzilimizga)"

    def add_arguments(self, parser):
        parser.add_argument("base_url", type=str, help="Masalan: https://api.turdievakademiyasi.uz")

    def handle(self, *args, **options):
        base_url = options["base_url"].rstrip("/")
        webhook_url = f"{base_url}/bot/webhook/{settings.TELEGRAM_WEBHOOK_SECRET}/"
        asyncio.run(bot.set_webhook(webhook_url, allowed_updates=["message", "callback_query"]))
        self.stdout.write(self.style.SUCCESS(f"Webhook o'rnatildi: {webhook_url}"))
