from rest_framework import permissions


class IsAdminStaff(permissions.BasePermission):
    """
    Admin panel API faqat Django ``is_staff=True`` foydalanuvchilar uchun ochiq
    (odatda ``createsuperuser`` bilan yaratilgan yoki Django adminda ``is_staff``
    belgisi qo'yilgan xodimlar). Mijozlar (TelegramUser) bu API bilan mutlaqo ishlamaydi.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class IsSuperUserForWrite(permissions.BasePermission):
    """
    O'qish (GET/HEAD/OPTIONS) — har qanday xodim (is_staff) uchun.
    Yozish (POST/PUT/PATCH/DELETE) — faqat superuser uchun.
    Xodim (admin panel foydalanuvchilari) ro'yxatini boshqarishda ishlatiladi —
    oddiy xodim boshqa xodimlarni o'chira olmasin/superuser qila olmasin.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_staff):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(user.is_superuser)
