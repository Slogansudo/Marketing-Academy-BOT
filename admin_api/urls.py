# JOYLASHTIRISH MANZILI: ACADEMY_BACK/admin_api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .auth_views import AdminLoginView, AdminLogoutView, AdminMeView
from .dashboard_views import (
    AdminDashboardView, AdminDashboardMonthlyAnalyticsView, AdminDashboardDailyAnalyticsView,
    AdminAutoRenewalStatsView, AdminRenewalSettingsView,
    AdminAdmissionSettingsView, AdminChannelSettingsView,
)
from . import viewsets as v
from bot import views


router = DefaultRouter()
router.register("staff-users", v.AdminStaffUserViewSet, basename="admin-staff-user")
router.register("users", v.TelegramUserViewSet, basename="admin-telegram-user")

router.register("subscription-plans", v.SubscriptionPlanViewSet, basename="admin-subscription-plan")
router.register("payment-cards", v.PaymentCardViewSet, basename="admin-payment-card")
router.register("subscriptions", v.SubscriptionViewSet, basename="admin-subscription")
router.register("payments", v.PaymentViewSet, basename="admin-payment")
router.register("pending-checkouts", v.PendingCheckoutViewSet, basename="admin-pending-checkout")
router.register("renewal-cycles", v.SubscriptionRenewalCycleViewSet, basename="admin-renewal-cycle")
router.register("renewal-attempts", v.RenewalAttemptViewSet, basename="admin-renewal-attempt")
router.register("renewal-retry-stages", v.RenewalRetryStageViewSet, basename="admin-renewal-retry-stage")
router.register("reminder-logs", v.PaymentReminderLogViewSet, basename="admin-reminder-log")

router.register("gift-months", v.GiftMonthViewSet, basename="admin-gift-month")
router.register("gift-progress", v.UserGiftProgressViewSet, basename="admin-gift-progress")
router.register("gift-claims", v.UserGiftClaimViewSet, basename="admin-gift-claim")

router.register("materials", v.MaterialViewSet, basename="admin-material")
router.register("content-categories", v.ContentCategoryViewSet, basename="admin-content-category")
router.register("contents", v.ContentViewSet, basename="admin-content")
router.register("content-likes", v.ContentLikeViewSet, basename="admin-content-like")
router.register("community-categories", v.CommunityCategoryViewSet, basename="admin-community-category")
router.register("community-contents", v.CommunityContentViewSet, basename="admin-community-content")

router.register("bot-messages", v.BotMessageViewSet, basename="admin-bot-message")
router.register("bot-message-categories", v.FunnelCategoryViewSet, basename="admin-bot-message-category")
router.register("bot-media", v.BotMediaViewSet, basename="admin-bot-media")
router.register("bot-links", v.BotLinkViewSet, basename="admin-bot-link")

router.register("referral-links", v.ReferralLinkViewSet, basename="admin-referral-link")

router.register("broadcasts", v.BroadcastViewSet, basename="admin-broadcast")
router.register("broadcast-recipients", v.BroadcastRecipientViewSet, basename="admin-broadcast-recipient")

urlpatterns = [
    path("auth/login/", AdminLoginView.as_view(), name="admin-auth-login"),
    path("auth/logout/", AdminLogoutView.as_view(), name="admin-auth-logout"),
    path("auth/me/", AdminMeView.as_view(), name="admin-auth-me"),
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("dashboard/monthly/", AdminDashboardMonthlyAnalyticsView.as_view(), name="admin-dashboard-monthly"),
    path("dashboard/daily/", AdminDashboardDailyAnalyticsView.as_view(), name="admin-dashboard-daily"),
    path("dashboard/auto-renewal/", AdminAutoRenewalStatsView.as_view(), name="admin-dashboard-auto-renewal"),
    path("renewal-settings/", AdminRenewalSettingsView.as_view(), name="admin-renewal-settings"),
    path("admission-settings/", AdminAdmissionSettingsView.as_view(), name="admin-admission-settings"),
    path("channel-settings/", AdminChannelSettingsView.as_view(), name="admin-channel-settings"),
    path("", include(router.urls)),

    ####
    path("bot/views/", AdminMeView.as_view(), name="admifn-me-view"),

]