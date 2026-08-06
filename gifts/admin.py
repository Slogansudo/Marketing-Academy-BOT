from django.contrib import admin
from .models import GiftMonth, UserGiftProgress, UserGiftClaim


@admin.register(GiftMonth)
class GiftMonthAdmin(admin.ModelAdmin):
    list_display = ("month_number", "tier_name", "gift_name", "is_active")
    list_editable = ("is_active",)
    ordering = ("month_number",)


@admin.register(UserGiftProgress)
class UserGiftProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "current_streak_months", "highest_streak_months", "streak_broken_count", "updated_at")
    search_fields = ("user__full_name", "user__telegram_id")


@admin.register(UserGiftClaim)
class UserGiftClaimAdmin(admin.ModelAdmin):
    list_display = ("user", "gift_month", "claimed_at")
    search_fields = ("user__full_name", "user__telegram_id")
