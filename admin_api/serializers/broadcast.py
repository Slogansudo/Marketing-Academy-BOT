from rest_framework import serializers

from broadcast.models import Broadcast, BroadcastRecipient


class BroadcastSerializer(serializers.ModelSerializer):
    target_plan_title = serializers.CharField(source="target_plan.title", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Broadcast
        fields = [
            "id", "title", "text", "image", "video", "is_video_note", "button_text", "button_url",
            "target_type", "target_plan", "target_plan_title", "custom_users", "status", "status_display",
            "scheduled_at", "total_recipients", "sent_count", "failed_count", "created_at", "sent_at",
            "image_file_id", "video_file_id",
        ]
        read_only_fields = [
            "status", "total_recipients", "sent_count", "failed_count", "sent_at",
            "image_file_id", "video_file_id",
        ]

    def to_internal_value(self, data):
        # FormData orqali yuborilganda (fayl bilan birga) bo'sh qiymat null emas, "" bo'lib keladi —
        # DateTimeField buni xato deb hisoblaydi, shuning uchun bu yerda null'ga aylantiramiz.
        if hasattr(data, "get") and data.get("scheduled_at", None) == "":
            data = data.copy()
            data["scheduled_at"] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        is_video_note = attrs.get("is_video_note", getattr(self.instance, "is_video_note", False))
        video = attrs.get("video", getattr(self.instance, "video", None))
        if is_video_note and not video:
            raise serializers.ValidationError(
                {"is_video_note": "Dumaloq video xabar uchun avval video yuklang."}
            )
        scheduled_at = attrs.get("scheduled_at", getattr(self.instance, "scheduled_at", None))
        if scheduled_at:
            from django.utils import timezone
            if scheduled_at <= timezone.now():
                raise serializers.ValidationError({"scheduled_at": "Rejalashtirilgan vaqt kelajakda bo'lishi kerak."})
        return attrs


class BroadcastRecipientSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.__str__", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    user_phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = BroadcastRecipient
        fields = [
            "id", "broadcast", "user", "user_display", "user_full_name", "user_phone_number",
            "user_username", "is_sent", "error", "sent_at",
        ]