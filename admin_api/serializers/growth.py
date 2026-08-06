# JOYLASHTIRISH MANZILI: ACADEMY_BACK/admin_api/serializers/growth.py

from rest_framework import serializers

from growth.models import AdmissionSettings, ReferralLink


class AdmissionSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdmissionSettings
        fields = ["id", "is_open", "allow_referral_when_closed", "updated_at", "updated_by"]
        read_only_fields = ["updated_at", "updated_by"]


class ReferralLinkSerializer(serializers.ModelSerializer):
    start_link = serializers.CharField(read_only=True)

    class Meta:
        model = ReferralLink
        fields = [
            "id", "code", "label", "is_active", "leads_count", "sales_count",
            "start_link", "created_at", "updated_at",
        ]
        read_only_fields = ["leads_count", "sales_count", "created_at", "updated_at"]