from aiogram import Router, F
from aiogram.types import Message

router = Router()


@router.message(F.web_app_data)
async def on_web_app_data(message: Message):
    """
    Mini app ichidan (masalan sovg'a olingandan keyin) `Telegram.WebApp.sendData(...)`
    orqali kelishi mumkin bo'lgan hodisalar shu yerda qabul qilinadi. Hozircha mini app
    barcha amallarni to'g'ridan-to'g'ri Django REST API orqali bajaradi (api), shuning
    uchun bu handler kelajakda push-tipidagi bildirishnomalar (masalan, 'sovg'a jo'natildi')
    uchun zaxira sifatida qoldirilgan.
    """
    await message.answer("Qabul qilindi ✅")
