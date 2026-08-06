# JOYLASHTIRISH MANZILI: ACADEMY_BACK/bot/handlers/registration.py

import re

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from users.models import TelegramUser
from cms.services import asend_group_step
from bot.states import Registration
from bot.keyboards import phone_request_keyboard, remove_keyboard, join_academy_keyboard, main_menu_keyboard
from subscriptions.services.subscription_service import user_has_active_subscription
from growth.services import aresolve_referral_link, aregister_lead, ais_admission_open

router = Router()

PHONE_RE = re.compile(r"^\+998\d{9}$")


async def _send_offer(message: Message):
    """
    3-rasm: video kontent + taklif matni + 'Akademiyaga qo'shilish' tugmasi.
    Ro'yxatdan o'tgan, lekin hali tarif tanlab to'lov qilmagan (yoki obunasi tugagan)
    foydalanuvchiga har safar /start bosganda shu ekran ko'rsatiladi — asosiy menyu emas.
    """
    await asend_group_step(message, "payment", "offer_intro", reply_markup=join_academy_keyboard())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    """
    1-bosqich: mijoz /start bosadi.
    7-bosqich: to'lovdan keyin Payme/Tribute sahifasidagi 'botga qaytish' havolasi
    `t.me/<bot>?start=paid` ko'rinishida bo'lgani uchun Telegram buni avtomatik /start
    sifatida yuboradi — shu holatda, agar to'lov haqiqatan ham muvaffaqiyatli bo'lib
    obuna faollashgan bo'lsa, ro'yxatdan o'tgan foydalanuvchiga to'g'ridan-to'g'ri
    asosiy menyu (9-rasm) ko'rsatiladi.

    MUHIM: ro'yxatdan o'tgan bo'lsa-da, hali tarif tanlab to'lov qilmagan (yoki
    obunasi muddati tugagan) foydalanuvchiga asosiy menyu HECH QACHON ko'rsatilmaydi —
    unga qayta taklif (offer) ekrani ko'rsatiladi.

    QABUL/REFERAL: `/start <kod>` ko'rinishida kelgan argument (masalan reklama
    havolasidagi `?start=VSL1`) referal havolaga moslanadi — topilsa lid sifatida
    hisoblanadi (faqat foydalanuvchi ENDI birinchi marta yaratilganda) va
    `TelegramUser.referral_source`ga yozib qo'yiladi. Admin qabulni yopgan bo'lsa,
    HALI RO'YXATDAN O'TMAGAN foydalanuvchiga (faol referal orqali kirmagan bo'lsa)
    ro'yxatdan o'tish oqimi o'rniga "qabul yopiq" xabari ko'rsatiladi — allaqachon
    ro'yxatdan o'tgan/obunasi bor ishtirokchilarga bu HECH QANDAY ta'sir qilmaydi.
    """
    await state.clear()

    referral_link = await aresolve_referral_link(command.args)

    user, created = await TelegramUser.objects.aget_or_create(
        telegram_id=message.from_user.id,
        defaults={"username": message.from_user.username},
    )

    if created and referral_link:
        user.referral_source = referral_link
        await user.asave(update_fields=["referral_source"])
        await aregister_lead(referral_link)

    if user.is_registered:
        if await user_has_active_subscription(user):
            await asend_group_step(message, "main_menu", "main_menu", reply_markup=await main_menu_keyboard())
            return

        # Obuna sotib olinmagan yoki tugagan — asosiy menyu o'rniga qayta taklif ko'rsatiladi.
        await _send_offer(message)
        return

    if not await ais_admission_open(referral_link):
        await asend_group_step(message, "admission", "admission_closed")
        return

    user.registration_step = TelegramUser.RegistrationStep.WAITING_NAME
    await user.asave(update_fields=["registration_step"])

    await asend_group_step(message, "onboarding", "ask_name", reply_markup=remove_keyboard())
    await state.set_state(Registration.waiting_name)


@router.message(Registration.waiting_name, F.text)
async def process_name(message: Message, state: FSMContext):
    user = await TelegramUser.objects.aget(telegram_id=message.from_user.id)
    user.full_name = message.text.strip()
    user.registration_step = TelegramUser.RegistrationStep.WAITING_PHONE
    await user.asave(update_fields=["full_name", "registration_step"])

    await asend_group_step(message, "onboarding", "ask_phone", reply_markup=phone_request_keyboard())
    await state.set_state(Registration.waiting_phone)


@router.message(Registration.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    """Pastdagi tugma orqali avto yuborilgan telefon (o'z raqami bo'lishi shart)."""
    if message.contact.user_id and message.contact.user_id != message.from_user.id:
        await message.answer("Iltimos, faqat o'zingizning telefon raqamingizni yuboring.")
        return
    await _finish_phone_step(message, state, message.contact.phone_number)


@router.message(Registration.waiting_phone, F.text.regexp(PHONE_RE))
async def process_phone_text(message: Message, state: FSMContext):
    """Qo'lda +998901234567 ko'rinishida yozilgan raqam."""
    await _finish_phone_step(message, state, message.text.strip())


@router.message(Registration.waiting_phone)
async def process_phone_invalid(message: Message):
    await message.answer(
        "Raqam formati noto'g'ri. Namuna: +998901234567 yoki pastdagi tugmani bosing 👇",
        reply_markup=phone_request_keyboard(),
    )


async def _finish_phone_step(message: Message, state: FSMContext, phone: str):
    if not phone.startswith("+"):
        phone = f"+{phone}"

    user = await TelegramUser.objects.aget(telegram_id=message.from_user.id)
    user.phone_number = phone
    user.registration_step = TelegramUser.RegistrationStep.COMPLETED
    await user.asave(update_fields=["phone_number", "registration_step"])
    await state.clear()

    await asend_group_step(message, "onboarding", "phone_accepted", reply_markup=remove_keyboard())

    # 3-rasm: video kontent (agar admin panelda biriktirilgan bo'lsa) + statik taklif matni
    await _send_offer(message)