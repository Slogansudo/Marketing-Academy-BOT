from rest_framework import serializers

from gifts.models import GiftMonth
from content.models import Material, ContentCategory, Content, CommunityCategory, CommunityContent


class SubscriptionStatusSerializer(serializers.Serializer):
    """11-rasm: mini app tepasidagi karta + 15-rasm bot 'obuna holati' bilan bir xil ma'lumot manbai."""

    tier_name = serializers.CharField()
    status_label = serializers.CharField()
    is_active = serializers.BooleanField()
    next_payment_date = serializers.DateField(allow_null=True)
    auto_renew = serializers.BooleanField()
    masked_pan = serializers.CharField(allow_null=True)
    current_streak_months = serializers.IntegerField()
    total_months_in_track = serializers.IntegerField()


class GiftMonthSerializer(serializers.ModelSerializer):
    is_unlocked = serializers.SerializerMethodField()
    is_claimed = serializers.SerializerMethodField()

    class Meta:
        model = GiftMonth
        fields = ["id", "month_number", "tier_name", "gift_name", "gift_image", "is_unlocked", "is_claimed"]

    def get_is_unlocked(self, obj):
        streak = self.context["current_streak_months"]
        return obj.month_number <= max(streak, 1)

    def get_is_claimed(self, obj):
        claimed_month_numbers = self.context["claimed_month_numbers"]
        return obj.month_number in claimed_month_numbers


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "title", "file_link"]


class ContentCategorySerializer(serializers.ModelSerializer):
    has_children = serializers.SerializerMethodField()

    class Meta:
        model = ContentCategory
        fields = ["id", "name", "cover_image", "has_children"]

    def get_has_children(self, obj):
        return obj.children.filter(is_active=True).exists()


class ContentListSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Content
        fields = ["id", "title", "cover_image", "media_type", "published_date", "is_liked"]

    def get_is_liked(self, obj):
        liked_ids = self.context.get("liked_content_ids", set())
        return obj.id in liked_ids


class ContentDetailSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name")

    class Meta:
        model = Content
        fields = [
            "id", "title", "cover_image", "description", "media_type",
            "media_file", "media_url", "published_date", "category_name", "is_liked",
        ]

    def get_is_liked(self, obj):
        liked_ids = self.context.get("liked_content_ids", set())
        return obj.id in liked_ids


class CommunityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityCategory
        fields = ["id", "name", "description", "external_link"]


class CommunityContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityContent
        fields = ["id", "title", "description", "image"]