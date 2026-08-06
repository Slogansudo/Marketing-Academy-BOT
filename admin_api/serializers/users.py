from django.contrib.auth.models import User
from rest_framework import serializers

from users.models import TelegramUser


class TelegramUserSerializer(serializers.ModelSerializer):
    is_registered = serializers.BooleanField(read_only=True)
    subscription_status = serializers.SerializerMethodField()
    subscription_plan_name = serializers.SerializerMethodField()
    current_streak_months = serializers.SerializerMethodField()
    gift_tier_name = serializers.SerializerMethodField()

    class Meta:
        model = TelegramUser
        fields = [
            "id", "telegram_id", "username", "full_name", "phone_number",
            "registration_step", "is_registered", "bot_state", "is_blocked_bot",
            "subscription_status", "subscription_plan_name",
            "current_streak_months", "gift_tier_name", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "bot_state"]

    def get_subscription_status(self, obj):
        sub = getattr(obj, "subscription", None)
        return sub.status if sub else None

    def get_subscription_plan_name(self, obj):
        sub = getattr(obj, "subscription", None)
        return sub.plan.title if sub and sub.plan_id else None

    def get_current_streak_months(self, obj):
        progress = getattr(obj, "gift_progress", None)
        return progress.current_streak_months if progress else 0

    def get_gift_tier_name(self, obj):
        # api/views.py SubscriptionStatusView bilan bir xil formula — mijozning joriy
        # sovg'a "darajasi" (Boshlovchi/O'quvchi/Talaba...).
        from gifts.models import GiftMonth

        streak = self.get_current_streak_months(obj)
        tier = (
            GiftMonth.objects.filter(is_active=True, month_number=max(streak, 1)).first()
            or GiftMonth.objects.filter(is_active=True).order_by("month_number").first()
        )
        return tier.tier_name if tier else None


class AdminStaffUserSerializer(serializers.ModelSerializer):
    """
    Django ``auth.User`` — bular admin panelga (bu API'ga) kiradigan xodimlar,
    TelegramUser (bot mijozlari) bilan chalkashtirilmasin.
    """

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "password", "first_name", "last_name", "email",
            "is_staff", "is_superuser", "is_active", "last_login", "date_joined",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance