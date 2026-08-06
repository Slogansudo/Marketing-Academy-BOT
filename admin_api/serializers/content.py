from rest_framework import serializers

from content.models import (
    Material, ContentCategory, Content, ContentLike, CommunityCategory, CommunityContent,
)


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "title", "file_link", "position", "is_active"]


class ContentCategorySerializer(serializers.ModelSerializer):
    content_count = serializers.IntegerField(source="contents.count", read_only=True)
    children_count = serializers.IntegerField(source="children.count", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True, default=None)

    class Meta:
        model = ContentCategory
        fields = [
            "id", "name", "cover_image", "parent", "parent_name", "position", "is_active",
            "content_count", "children_count",
        ]

    def validate(self, attrs):
        instance = self.instance
        parent = attrs.get("parent", instance.parent if instance else None)

        if parent is not None:
            if instance and parent.id == instance.id:
                raise serializers.ValidationError({"parent": "Kategoriya o'z-o'ziga ichki kategoriya bo'la olmaydi."})
            if instance and instance.id in parent.get_ancestor_ids():
                raise serializers.ValidationError(
                    {"parent": "Kategoriyani o'zining ichki (avlod) kategoriyasi ostiga ko'chirib bo'lmaydi — bu aylanma bog'lanish hosil qiladi."}
                )
            if parent.contents.exists():
                raise serializers.ValidationError(
                    {"parent": "Bu kategoriyada allaqachon kontentlar bor, uning ichiga yana kategoriya qo'shib bo'lmaydi."}
                )
            if instance and instance.children.exists():
                raise serializers.ValidationError(
                    {"parent": "Bu kategoriyaning o'z ichki kategoriyalari bor, uni boshqa kategoriya ichiga ko'chirib bo'lmaydi."}
                )
        return attrs


class ContentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    # 1-daraja (TOP) kategoriya nomi — filtrlangan/tekislangan ro'yxatda (kategoriya
    # ichiga kirmasdan) admin qaysi bo'limga tegishli ekanini ko'rishi uchun.
    top_category_name = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source="likes.count", read_only=True)

    class Meta:
        model = Content
        fields = [
            "id", "category", "category_name", "top_category_name", "title", "cover_image", "description",
            "media_type", "media_file", "media_url", "published_date", "position",
            "is_active", "likes_count",
        ]

    def get_top_category_name(self, obj):
        return obj.category.get_root().name

    def validate_category(self, category):
        if category.children.exists():
            raise serializers.ValidationError(
                "Bu kategoriyaning ichida kichik kategoriyalar bor — kontent faqat kichik kategoriyaning o'ziga qo'shiladi."
            )
        return category


class ContentLikeSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.__str__", read_only=True)
    content_title = serializers.CharField(source="content.title", read_only=True)

    class Meta:
        model = ContentLike
        fields = ["id", "user", "user_display", "content", "content_title", "created_at"]


class CommunityCategorySerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = CommunityCategory
        fields = ["id", "name", "description", "external_link", "position", "is_active", "item_count"]


class CommunityContentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = CommunityContent
        fields = ["id", "category", "category_name", "title", "description", "image", "position", "is_active"]