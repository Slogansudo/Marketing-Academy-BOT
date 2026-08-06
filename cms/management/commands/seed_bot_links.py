from django.core.management.base import BaseCommand
from cms.models import BotLink


DEFAULT_LINKS = {
    BotLink.Key.PRIVATE_CHANNEL: "https://t.me/+placeholder_channel",
    BotLink.Key.HELP: "https://t.me/placeholder_support",
    BotLink.Key.COMMUNITY_CHAT: "https://t.me/placeholder_chat",
    BotLink.Key.OFFER_DOCUMENT: "https://docs.google.com/document/d/placeholder/edit",
}


class Command(BaseCommand):
    """
    Bot havolalarini (BotLink) boshlang'ich (default) qiymatlar bilan to'ldiradi.

    Bot matnlari endi statik (kod ichida, `cms.bot_texts`) — shuning uchun
    ular uchun seed kerak emas, faqat admin panelda tahrirlanadigan havolalar seed qilinadi.
    """

    help = "Bot havolalarini boshlang'ich (default) qiymatlar bilan to'ldiradi"

    def handle(self, *args, **options):
        for key, url in DEFAULT_LINKS.items():
            obj, created = BotLink.objects.get_or_create(key=key, defaults={"url": url})
            self.stdout.write(f"{'yaratildi' if created else 'mavjud'}: {key}")

        self.stdout.write(self.style.SUCCESS("Seed yakunlandi."))
