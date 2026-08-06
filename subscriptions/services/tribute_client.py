"""
Tribute (https://tribute.tg) — Telegram-native to'lov/obuna platformasi.
Chet eldan (dollarda) to'lov va uning avtomatik yechilishi to'liq Tribute tomonida
boshqariladi; biz faqat:
  1. Mijozni Tribute mini-appiga (8-rasm) yo'naltiramiz (deep-link).
  2. Tribute webhook orqali "new_subscription" / "cancelled_subscription" /
     "recurring_payment" eventlarini bizga yuboradi -> shu asosda Subscription/Payment
     yozuvlarini yangilaymiz (webhooks.py da ko'ring).
"""

from django.conf import settings


class TributeClient:
    def __init__(self):
        self.api_key = settings.TRIBUTE_API_KEY

    def build_subscription_link(self, plan_external_id: str, checkout_uuid: str) -> str:
        """
        5-bosqich: 'Chet eldan to'lash' bosilganda ochiladigan Tribute havolasi.
        checkout_uuid `PendingCheckout` orqali payload/label sifatida uzatiladi, shunda
        webhook kelganda foydalanuvchini aniqlaymiz.
        """
        return f"https://t.me/tribute/app?startapp={plan_external_id}_{checkout_uuid}"

    def cancel_subscription(self, tribute_external_id: str) -> None:
        # TODO(prod): Tribute API orqali obunani bekor qilish (agar Tribute buni qo'llab-quvvatlasa;
        # aks holda mijozga Tribute ilovasi ichida bekor qilishni tavsiya qilamiz).
        raise NotImplementedError
