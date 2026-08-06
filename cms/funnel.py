# JOYLASHTIRISH MANZILI: ACADEMY_BACK/cms/funnel.py

"""
Bot xabar konstruktori — DINAMIK VORONKA arxitekturasi (2-avlod).

Eski arxitekturada (`cms/bot_texts.py` docstringiga qarang) har bir kategoriya
ICHIDAGI xabarlar ham, ularning soni/tartibi ham to'liq kod bilan qattiq
belgilangan edi. Bu modul bilan boshlanadigan yangi qatlamda:

  - Kategoriya (`BotMessageTemplate.Group`) hamon kod tomonidan belgilangan
    haqiqiy ulanish nuqtasini anglatadi (masalan "onboarding" — ro'yxatdan
    o'tish handlerlari ishlaydigan joy) — buni admin panel orqali yaratib yoki
    o'chirib bo'lmaydi, chunki har biri botning muayyan hodisasiga jismonan
    bog'langan.
  - Lekin har bir kategoriya ICHIDA endi xabarlar (`BotMessageTemplate`
    qatorlari, `step_type=custom`) to'liq dinamik: admin ularni qo'sha oladi,
    o'chira oladi, tartiblay oladi — kodni o'zgartirmasdan.
  - Kategoriyalar orasidagi MANTIQIY BOG'LIQLIK (masalan "asosiy menyu"
    "ro'yxatdan o'tish" tugagandan keyin keladi, aksincha emas) shu yerda,
    kod ichida, deklarativ tarzda belgilanadi. Bu DB'da emas — chunki bu
    haqiqiy bot oqimining o'zgarmas tuzilishi, admin buni o'zgartira olmaydi,
    faqat shu bog'liqlikni BUZMAYDIGAN darajada kategoriyalar tartibini
    (bo'limlar ekranda qaysi tartibda ko'rinishini) va har bir kategoriya
    ichidagi xabarlarni tartiblay oladi.
"""

from __future__ import annotations

from django.db.models import TextChoices

# --- Kategoriyalar orasidagi bog'liqlik grafigi -----------------------------
# `category -> [shu kategoriya ishlashi uchun avval TUGAGAN bo'lishi shart
# bo'lgan kategoriyalar ro'yxati]`. Masalan "payment" "onboarding"ga bog'liq —
# demak "Taklif va to'lov" bo'limi "Ro'yxatdan o'tish" bo'limidan OLDINGA
# surilishi mumkin emas.
CATEGORY_DEPENDENCIES: dict[str, list[str]] = {
    "onboarding": [],
    "payment": ["onboarding"],
    "main_menu": ["onboarding", "payment"],
    "renewal_reminders": ["onboarding", "payment"],
    "renewal_fail_cascade": ["onboarding", "payment"],
    "admission": [],
}


def _all_dependencies(category: str, _seen: set[str] | None = None) -> set[str]:
    """`category` bog'liq bo'lgan BARCHA kategoriyalar (transitiv, ya'ni
    bog'liqning bog'liqlari ham hisobga olinadi)."""
    _seen = _seen or set()
    for dep in CATEGORY_DEPENDENCIES.get(category, []):
        if dep not in _seen:
            _seen.add(dep)
            _seen |= _all_dependencies(dep, _seen)
    return _seen


def category_rank(category: str, _seen: set[str] | None = None) -> int:
    """Bog'liqlik zanjiridagi eng chuqur daraja (0 = hech kimga bog'liq emas).
    Kategoriyalarning "tabiiy" tartibini hisoblash uchun ishlatiladi."""
    _seen = _seen or set()
    if category in _seen:
        return 0
    deps = CATEGORY_DEPENDENCIES.get(category, [])
    if not deps:
        return 0
    return 1 + max(category_rank(d, _seen | {category}) for d in deps)


def dependency_violation(category: str, preceding_category: str) -> str | None:
    """
    Agar `preceding_category` ekranda/tartibda `category`dan OLDIN turishi
    KERAK bo'lsa-yu, lekin admin buni aksincha qilmoqchi bo'lsa (`category`ni
    `preceding_category`dan oldinga surmoqchi bo'lsa) — tushunarli xato matnini
    qaytaradi. Aks holda `None` (ruxsat etiladi).
    """
    if category == preceding_category:
        return None
    if preceding_category in _all_dependencies(category):
        return (
            f"'{category}' toifasi '{preceding_category}' toifasidan OLDINGA qo'yilishi "
            f"mumkin emas — tizim mantig'iga ko'ra, mijoz avval '{preceding_category}' "
            f"bosqichini bosib o'tishi shart."
        )
    return None


def validate_category_order(order: list[str]) -> str | None:
    """
    Butun voronka sahifasidagi kategoriyalar tartibini (yuqoridan pastga)
    tekshiradi. `order` — kategoriya kalitlarining, admin belgilamoqchi bo'lgan
    yangi tartibda, ro'yxati. Har bir kategoriya barcha o'z bog'liqlaridan
    KEYIN turishi kerak. Birinchi topilgan qoidabuzarlik matnini qaytaradi,
    hammasi to'g'ri bo'lsa `None`.
    """
    position = {cat: idx for idx, cat in enumerate(order)}
    for cat in order:
        for dep in CATEGORY_DEPENDENCIES.get(cat, []):
            if dep in position and position[dep] > position[cat]:
                return dependency_violation(cat, dep) or (
                    f"'{cat}' toifasi '{dep}' toifasidan oldin tura olmaydi."
                )
    return None


class TriggerEvent(TextChoices):
    """
    Avto-to'lov muvaffaqiyatsiz-urinish kaskadida (`renewal_fail_cascade`)
    har bir xabar qaysi HAQIQIY HODISAGA bog'langanini bildiradi. Faqat shu
    kategoriyada ma'noli — boshqa kategoriyalarda bo'sh qoladi.

    `ATTEMPT` uchun `attempt_number` (1..subscriptions.renewal_config.max_attempts())
    ko'rsatilishi shart — aynan shu urinish muvaffaqiyatsiz bo'lganda
    yuboriladi. Admin istagan urinish raqamiga xabar biriktirmasligi ham
    mumkin (masalan 2-urinishga hech qanday xabar qo'shmasa — o'sha
    urinishda mijozga umuman xabar bormaydi, bu tizim uchun xato emas).
    """

    ATTEMPT = "attempt", "Muayyan urinish raqami"
    CARD_EXPIRED = "card_expired", "Karta muddati o'tgan"
    CARD_CHANGE_REQUESTED = "card_change_requested", "Kaskad ichida 'Kartani almashtirish' bosilganda"
    SUCCESS = "success", "To'lov muvaffaqiyatli bo'ldi"
    CANCELLED = "cancelled", "Obuna bekor qilindi"
    IN_PROGRESS = "in_progress", "To'lov ishlanmoqda (alert)"


# Har bir kategoriya uchun ruxsat etilgan dinamik o'zgaruvchilar reestri —
# admin panel matn tahrirlash oynasidagi "+ O'zgaruvchi qo'shish" tanlagichi
# shu ro'yxatdan to'ldiriladi. E'TIBOR: nomlar bot xizmat qatlamidagi haqiqiy
# `.replace("{nomi}", ...)` chaqiruvlariga mos kelishi SHART — aks holda
# o'zgaruvchi jo'natilgan matnda xom holicha (`{nomi}`) qolib ketadi.
CATEGORY_VARIABLES: dict[str, list[tuple[str, str]]] = {
    "onboarding": [
        ("ism", "Foydalanuvchi ismi"),
        ("phone", "Telefon raqami"),
    ],
    "payment": [
        ("plan_title", "Tanlangan tarif nomi"),
        ("plan_lines", "Barcha tariflar ro'yxati (matn)"),
        ("price_uzs", "Narx, so'm"),
        ("price_usd", "Narx, USD"),
        ("offer_link", "Oferta hujjati havolasi"),
    ],
    "main_menu": [
        ("status", "Obuna holati matni"),
        ("next_date", "Keyingi to'lov sanasi"),
        ("autopay", "Avtomatik to'lov holati"),
        ("masked_pan", "Yashiringan karta raqami"),
        ("plan_title", "Joriy tarif nomi"),
        ("price", "Joriy tarif narxi"),
    ],
    "renewal_reminders": [
        ("tarif_name", "Tarif nomi"),
        ("expires_at", "Obuna tugash sanasi"),
    ],
    "renewal_fail_cascade": [
        ("tarif_name", "Tarif nomi"),
        ("amount", "Summasi, so'm"),
        ("error_reason", "Xatolik sababi"),
        ("expires_at", "Obuna tugash sanasi"),
    ],
    "admission": [],
}


def available_variables(category: str) -> list[dict]:
    return [{"key": key, "label": label} for key, label in CATEGORY_VARIABLES.get(category, [])]
