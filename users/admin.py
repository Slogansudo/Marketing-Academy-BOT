from django.contrib import admin
from .models import TelegramUser


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "username", "telegram_id", "phone_number", "registration_step", "is_blocked_bot", "created_at")
    list_filter = ("registration_step", "is_blocked_bot")
    search_fields = ("full_name", "username", "telegram_id", "phone_number")
    readonly_fields = ("telegram_id", "created_at", "updated_at")
