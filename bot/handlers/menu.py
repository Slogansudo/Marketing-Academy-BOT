# JOYLASHTIRISH MANZILI: ACADEMY_BACK/bot/handlers/menu.py

from aiogram import Router, F
from aiogram.types import CallbackQuery

from cms.bot_texts import get_bot_text
from cms.services import asend_trailing_customs
from bot.keyboards import main_menu_keyboard
from subscriptions.services.subscription_service import user_has_active_subscription

router = Router()


@router.callback_query(F.data == "back_to_menu")
async def on_back_to_menu(callback: CallbackQuery):
    """9-rasm: 'Menyuga qaytish' — obuna holati/kartani almashtirish sahifalaridan qaytish.

    Himoya: obunasi tugab qolgan (masalan avtomatik to'lov muvaffaqiyatsiz bo'lgan)
    foydalanuvchi eski xabardagi tugmani bossa ham, asosiy menyu qayta ko'rsatilmaydi.

    'main_menu' ekrani mavjud xabarni TAHRIRLAYDI (yangi xabar emas), shuning uchun
    admin konstruktorda shu kartadan KEYIN qo'shgan bo'lishi mumkin bo'lgan CUSTOM
    xabar(lar) alohida, YANGI xabar(lar) sifatida, tahrirlangan xabardan keyin
    yuboriladi (`asend_trailing_customs`).
    """
    from users.models import TelegramUser

    user = await TelegramUser.objects.aget(telegram_id=callback.from_user.id)
    if not await user_has_active_subscription(user):
        await callback.answer(
            "Obunangiz faol emas. Davom etish uchun /start buyrug'ini bosing.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        get_bot_text("main_menu"),
        reply_markup=await main_menu_keyboard(),
    )
    await asend_trailing_customs(callback.message, "main_menu", "main_menu")
    await callback.answer()