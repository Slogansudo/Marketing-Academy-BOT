# JOYLASHTIRISH MANZILI: ACADEMY_BACK/admin_api/serializers/subscriptions.py

from rest_framework import serializers

from subscriptions.models import (
    SubscriptionPlan, PaymentCard, Subscription, Payment, PendingCheckout,
    SubscriptionRenewalCycle, RenewalAttempt, PaymentReminderLog, RenewalSettings,
    RenewalRetryStage,
)


class RenewalSettingsSerializer(serializers.ModelSerializer):
    """
    Avto-to'lov ESLATMA vaqt sozlamalari (singleton) — to'lovdan oldingi 1/2/3-kun
    eslatmalari va SMS bosqichi. Qayta urinish oralig'i/jami urinishlar soni ENDI
    bu yerda emas — to'liq dinamik (`RenewalRetryStageSerializer`, quyida) orqali
    boshqariladi. Qarang: `subscriptions/renewal_config.py`.
    """

    max_attempts = serializers.SerializerMethodField()

    class Meta:
        model = RenewalSettings
        fields = [
            "id",
            "reminder_stage_1_days", "reminder_stage_2_days", "reminder_stage_3_days", "sms_on_stage",
            "max_attempts", "updated_at", "updated_by",
        ]
        read_only_fields = ["updated_at", "updated_by"]

    def get_max_attempts(self, obj):
        """O'qish uchun qulaylik: joriy jami urinishlar soni (`RenewalRetryStage`
        qatorlar soni + 1) — bu yerda tahrirlanmaydi, faqat ma'lumot uchun."""
        from subscriptions.renewal_config import max_attempts as compute_max_attempts

        return compute_max_attempts()

    def validate(self, attrs):
        def get(name):
            return attrs.get(name, getattr(self.instance, name, None))

        d1, d2, d3 = get("reminder_stage_1_days"), get("reminder_stage_2_days"), get("reminder_stage_3_days")
        if not (d1 > d2 > d3):
            raise serializers.ValidationError(
                "Eslatma kunlari kamayib borishi kerak: 1-bosqich > 2-bosqich > 3-bosqich "
                f"(hozir: {d1} > {d2} > {d3} emas). Aks holda eslatmalar noto'g'ri ketma-ketlikda ketadi."
            )
        sms_stage = get("sms_on_stage")
        if sms_stage not in (0, 1, 2, 3):
            raise serializers.ValidationError("sms_on_stage faqat 0 (o'chirilgan), 1, 2 yoki 3 bo'lishi mumkin.")
        return attrs


class RenewalRetryStageSerializer(serializers.ModelSerializer):
    """
    Avto-to'lov qayta urinish bosqichlaridan BITTASI — "N-urinish muvaffaqiyatsiz
    bo'lsa, keyingisigacha necha soat kutilsin". `attempt_number` o'qish uchun —
    ketma-ketlik buzilmasligi uchun faqat server tomonidan avtomatik beriladi
    (yaratishda ketma-ket keyingi raqam, `RenewalRetryStageViewSet.create`ga qarang).

    `message_slug`/`message_title` — shu urinishga admin konstruktorda ("Bot
    xabarlari") biriktirilgan xabar haqida qulaylik uchun ma'lumot (front-end shu
    yerdan to'g'ridan-to'g'ri matnga havola bera oladi).
    """

    message_slug = serializers.SerializerMethodField()
    message_title = serializers.SerializerMethodField()
    has_message = serializers.SerializerMethodField()

    class Meta:
        model = RenewalRetryStage
        fields = [
            "id", "attempt_number", "wait_hours",
            "message_slug", "message_title", "has_message",
            "updated_at", "updated_by",
        ]
        read_only_fields = ["attempt_number", "updated_at", "updated_by"]

    def _linked_message(self, obj):
        from cms.models import BotMessageTemplate

        return (
            BotMessageTemplate.objects.filter(
                group=BotMessageTemplate.CASCADE_GROUP,
                trigger_event="attempt",
                attempt_number=obj.attempt_number,
            )
            .order_by("position")
            .first()
        )

    def get_message_slug(self, obj):
        msg = self._linked_message(obj)
        return msg.slug if msg else None

    def get_message_title(self, obj):
        msg = self._linked_message(obj)
        return msg.title if msg else None

    def get_has_message(self, obj):
        return self._linked_message(obj) is not None

    def validate_wait_hours(self, value):
        from subscriptions.renewal_config import MIN_RETRY_HOURS, MAX_RETRY_HOURS

        if not (MIN_RETRY_HOURS <= value <= MAX_RETRY_HOURS):
            raise serializers.ValidationError(
                f"Kutish vaqti {MIN_RETRY_HOURS}-{MAX_RETRY_HOURS} soat oralig'ida bo'lishi kerak."
            )
        return value


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ["id", "title", "duration_months", "price_uzs", "price_usd", "is_active", "position"]


class PaymentCardSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.__str__", read_only=True)

    class Meta:
        model = PaymentCard
        fields = ["id", "user", "user_display", "masked_pan", "payme_card_token", "is_primary", "created_at"]
        extra_kwargs = {
            # Token maxfiy — ro'yxatda/detailda ko'rsatilmaydi, lekin admin kerak bo'lsa
            # (masalan qo'lda tuzatish) yozishi mumkin.
            "payme_card_token": {"write_only": True},
        }


class SubscriptionSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.__str__", read_only=True)
    plan_title = serializers.CharField(source="plan.title", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    masked_pan = serializers.CharField(source="card.masked_pan", read_only=True, default=None)

    class Meta:
        model = Subscription
        fields = [
            "id", "user", "user_display", "plan", "plan_title", "status", "status_display",
            "provider", "card", "masked_pan", "tribute_external_id", "started_at",
            "next_payment_date", "auto_renew", "created_at", "updated_at",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="subscription.user.__str__", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "subscription", "user_display", "amount", "currency", "provider", "status",
            "external_transaction_id", "is_recurring_charge", "paid_at", "created_at",
        ]


class PendingCheckoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingCheckout
        fields = [
            "id", "checkout_uuid", "user", "plan", "provider", "purpose", "renewal_cycle",
            "is_used", "created_at", "expires_at", "pending_masked_pan", "verify_attempts",
        ]
        read_only_fields = ["checkout_uuid", "pending_card_token", "pending_masked_pan", "verify_attempts"]


class RenewalAttemptSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="cycle.subscription.user.__str__", read_only=True)
    plan_title = serializers.CharField(source="cycle.subscription.plan.title", read_only=True)
    subscription = serializers.IntegerField(source="cycle.subscription_id", read_only=True)
    due_date = serializers.DateField(source="cycle.due_date", read_only=True)
    phone_number = serializers.CharField(source="cycle.subscription.user.phone_number", read_only=True, default=None)

    class Meta:
        model = RenewalAttempt
        fields = [
            "id", "cycle", "subscription", "user_display", "plan_title", "phone_number", "due_date",
            "attempt_number", "result", "error_reason", "payme_order_id", "payme_receipt_id", "attempted_at",
        ]


class SubscriptionRenewalCycleSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="subscription.user.__str__", read_only=True)
    attempts = RenewalAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = SubscriptionRenewalCycle
        fields = [
            "id", "subscription", "user_display", "due_date", "status", "attempt_number",
            "next_attempt_at", "locked_at", "last_result", "last_error_reason",
            "attempts", "created_at", "updated_at",
        ]
        read_only_fields = ["locked_at"]


class PaymentReminderLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentReminderLog
        fields = ["id", "subscription", "due_date", "reminder_type", "days_before", "sent_at"]