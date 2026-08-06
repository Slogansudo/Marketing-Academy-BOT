from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    """1-2-bosqich: ism va telefon so'rash."""
    waiting_name = State()
    waiting_phone = State()


class CardChangeFlow(StatesGroup):
    """15-bosqich: 'Kartani almashtirish' bosilgandan keyin kutish holati (havola tashqarida ochiladi,
    lekin webhook kelguncha botda 'kutmoqda' holatini saqlab turamiz, kerak bo'lsa)."""
    waiting_confirmation = State()
