from rest_framework import serializers

from gifts.models import GiftMonth, UserGiftProgress, UserGiftClaim


class GiftMonthSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftMonth
        fields = [
            "id", "month_number", "tier_name", "gift_name", "gift_image",
            "claim_link", "is_active",
        ]


class UserGiftProgressSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.__str__", read_only=True)

    class Meta:
        model = UserGiftProgress
        fields = [
            "id", "user", "user_display", "current_streak_months",
            "highest_streak_months", "streak_broken_count", "updated_at",
        ]


class UserGiftClaimSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.__str__", read_only=True)
    gift_name = serializers.CharField(source="gift_month.gift_name", read_only=True)

    class Meta:
        model = UserGiftClaim
        fields = ["id", "user", "user_display", "gift_month", "gift_name", "claimed_at"]
