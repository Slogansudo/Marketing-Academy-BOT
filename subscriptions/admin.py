# JOYLASHTIRISH MANZILI: ACADEMY_BACK/subscriptions/admin.py

from django.contrib import admin
from .models import (
    SubscriptionPlan, PaymentCard, Subscription, Payment, PendingCheckout,
    SubscriptionRenewalCycle, RenewalAttempt, PaymentReminderLog,
    RenewalSettings, RenewalRetryStage,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "duration_months", "price_uzs", "price_usd", "position", "is_active")
    list_editable = ("position", "is_active")
    ordering = ("position",)


@admin.register(PaymentCard)
class PaymentCardAdmin(admin.ModelAdmin):
    list_display = ("user", "masked_pan", "is_primary", "created_at")
    search_fields = ("user__full_name", "user__telegram_id", "masked_pan")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("amount", "currency", "provider", "status", "external_transaction_id", "paid_at", "created_at")
    can_delete = False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "provider", "next_payment_date", "auto_renew")
    list_filter = ("status", "provider", "plan", "auto_renew")
    search_fields = ("user__full_name", "user__telegram_id")
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("subscription", "amount", "currency", "provider", "status", "is_recurring_charge", "paid_at")
    list_filter = ("status", "provider", "is_recurring_charge")
    search_fields = ("subscription__user__full_name", "external_transaction_id")


@admin.register(PendingCheckout)
class PendingCheckoutAdmin(admin.ModelAdmin):
    list_display = ("checkout_uuid", "user", "plan", "provider", "purpose", "is_used", "created_at", "expires_at")
    list_filter = ("provider", "purpose", "is_used")


class RenewalAttemptInline(admin.TabularInline):
    model = RenewalAttempt
    extra = 0
    readonly_fields = ("attempt_number", "result", "error_reason", "payme_order_id", "payme_receipt_id", "attempted_at")
    can_delete = False


@admin.register(SubscriptionRenewalCycle)
class SubscriptionRenewalCycleAdmin(admin.ModelAdmin):
    list_display = ("subscription", "due_date", "status", "attempt_number", "next_attempt_at", "last_result")
    list_filter = ("status", "last_result")
    search_fields = ("subscription__user__full_name", "subscription__user__telegram_id")
    inlines = [RenewalAttemptInline]
    readonly_fields = ("locked_at",)


@admin.register(PaymentReminderLog)
class PaymentReminderLogAdmin(admin.ModelAdmin):
    list_display = ("subscription", "due_date", "reminder_type", "days_before", "sent_at")
    list_filter = ("reminder_type",)


@admin.register(RenewalSettings)
class RenewalSettingsAdmin(admin.ModelAdmin):
    """Odatda admin panel (React) orqali boshqariladi — bu yerda faqat qo'lda/favqulodda tuzatish uchun."""

    list_display = ("__str__", "reminder_stage_1_days", "reminder_stage_2_days", "reminder_stage_3_days", "sms_on_stage", "updated_at")

    def has_add_permission(self, request):
        return not RenewalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RenewalRetryStage)
class RenewalRetryStageAdmin(admin.ModelAdmin):
    """
    Odatda admin panel (React, "Bot xabarlari" sahifasidagi "Avto-to'lov vaqt
    sozlamalari" bo'limi) orqali boshqariladi — bu yerda faqat qo'lda/favqulodda
    tuzatish uchun. `attempt_number` tartibini buzmaslik uchun bu yerdan yangi
    qator qo'shish tavsiya etilmaydi (React panel orqali qo'shing — u bilan bog'liq
    bot xabarini ham avtomatik yaratadi).
    """

    list_display = ("attempt_number", "wait_hours", "updated_at", "updated_by")
    ordering = ("attempt_number",)
    readonly_fields = ("attempt_number",)