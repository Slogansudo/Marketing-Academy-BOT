"""
JOYLASHTIRISH MANZILI: ACADEMY_BACK/subscriptions/renewal_config.py

Avto to'lov (renewal) VAQT sozlamalari.

Eslatma kunlari va SMS bosqichi `subscriptions.RenewalSettings` (singleton, bazada
bitta qator) orqali admin panelda tahrirlanadi.

Qayta urinish oralig'i va jami urinishlar soni ENDI to'liq DINAMIK:
`subscriptions.RenewalRetryStage` jadvalidagi qatorlar soni + 1 = jami urinishlar
soni, har bir qatorning `wait_hours`i esa aynan o'sha urinish muvaffaqiyatsiz
bo'lganda keyingisigacha necha soat kutilishini bildiradi. Admin istalgan sondagi
bosqich qo'sha/o'chira oladi — qarang: `admin_api/viewsets.RenewalRetryStageViewSet`.

Bazada hali qator yo'q bo'lsa (masalan migratsiya hali ishlamagan), pastdagi
statik DEFAULT_* qiymatlarga tushiladi — bot hech qachon shu sabab yiqilib qolmaydi.

MUHIM DIZAYN QOIDASI: bot xabar qatlamida QAYSI matn yuborilishi hamon URINISH
RAQAMI (`attempt_number`) bo'yicha ishlaydi, soat QIYMATI bo'yicha emas — admin
kutish vaqtini o'zgartirsa ham, mos matn hech qachon "topilmadi" xatosiga
uchramaydi.
"""

DEFAULT_REMINDER_STAGE_DAYS = {1: 3, 2: 2, 3: 1}
DEFAULT_SMS_ON_STAGE = 3
DEFAULT_RETRY_WAIT_HOURS = {1: 24, 2: 24, 3: 18, 4: 6}
DEFAULT_MAX_ATTEMPTS = len(DEFAULT_RETRY_WAIT_HOURS) + 1

# Admin panelda ruxsat etilgan chegaralar (serializer/viewset validatsiyasida ham ishlatiladi).
MIN_REMINDER_DAYS, MAX_REMINDER_DAYS = 1, 30
MIN_RETRY_HOURS, MAX_RETRY_HOURS = 1, 240
# Nechta qayta-urinish BOSQICHI (RenewalRetryStage qatori) bo'lishi mumkin — jami
# urinishlar soni bundan bittaga ko'p (1 dastlabki urinish + shu qadar qayta urinish).
MAX_RETRY_STAGES = 11
MIN_MAX_ATTEMPTS, MAX_MAX_ATTEMPTS = 2, MAX_RETRY_STAGES + 1


def _settings():
    from subscriptions.models import RenewalSettings

    try:
        return RenewalSettings.load()
    except Exception:  # noqa: BLE001 — masalan migratsiya hali ishlamagan bo'lsa
        return None


def reminder_stage_days(stage: int) -> int:
    """1/2/3-eslatma to'lov sanasidan necha kun oldin yuborilishi."""
    s = _settings()
    if s is None:
        return DEFAULT_REMINDER_STAGE_DAYS.get(stage, 1)
    return {1: s.reminder_stage_1_days, 2: s.reminder_stage_2_days, 3: s.reminder_stage_3_days}.get(
        stage, DEFAULT_REMINDER_STAGE_DAYS.get(stage, 1)
    )


def all_reminder_stages() -> list[int]:
    """Har doim [1, 2, 3] — nechta bosqich borligi o'zgarmaydi, faqat kunlar soni tahrirlanadi."""
    return [1, 2, 3]


def sms_on_stage() -> int:
    """Qaysi bosqichda SMS ham yuborilsin (0 = o'chirilgan)."""
    s = _settings()
    return DEFAULT_SMS_ON_STAGE if s is None else s.sms_on_stage


def retry_wait_hours(attempt_number: int) -> int:
    """`attempt_number`-urinish muvaffaqiyatsiz bo'lsa, keyingisigacha necha soat
    kutilishi — to'liq dinamik `RenewalRetryStage` jadvalidan olinadi."""
    from subscriptions.models import RenewalRetryStage

    try:
        return RenewalRetryStage.wait_hours_for(attempt_number)
    except Exception:  # noqa: BLE001 — masalan migratsiya hali ishlamagan bo'lsa
        return DEFAULT_RETRY_WAIT_HOURS.get(attempt_number, DEFAULT_RETRY_WAIT_HOURS[max(DEFAULT_RETRY_WAIT_HOURS)])


def max_attempts() -> int:
    from subscriptions.models import RenewalRetryStage

    try:
        return RenewalRetryStage.max_attempts()
    except Exception:  # noqa: BLE001
        return DEFAULT_MAX_ATTEMPTS