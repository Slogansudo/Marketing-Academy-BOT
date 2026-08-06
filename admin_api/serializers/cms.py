# JOYLASHTIRISH MANZILI: ACADEMY_BACK/admin_api/serializers/cms.py

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from cms.models import BotMedia, BotLink, BotMessageTemplate, ChannelSettings, FunnelCategorySettings


class BotMediaSerializer(serializers.ModelSerializer):
    """
    Bot xabariga biriktiriladigan media — istalgan turdagi (video/audio/rasm) bo'lishi
    mumkin. Video uchun qo'shimcha ravishda shakl (to'rtburchak/dumaloq) tanlanadi.

    Fayl ALMASHTIRILGANDA eski fayl serverdan avtomatik o'chadi — bu model darajasida
    (`cms.models`dagi `pre_save`/`post_delete` signallar) ta'minlanadi, bu yerda faqat
    kirish ma'lumotlari (qaysi tur, qaysi shakl, fayl yoki URL) to'g'riligi tekshiriladi.
    """

    slug_display = serializers.SerializerMethodField()
    media_type_display = serializers.CharField(source="get_media_type_display", read_only=True)
    video_shape_display = serializers.CharField(source="get_video_shape_display", read_only=True)

    class Meta:
        model = BotMedia
        fields = [
            "id", "slug", "slug_display", "media_type", "media_type_display",
            "video_shape", "video_shape_display", "file", "video_url",
            "telegram_file_id", "updated_at",
        ]
        read_only_fields = ["telegram_file_id", "updated_at"]

    def get_slug_display(self, obj):
        """`slug` endi statik `choices`ga bog'liq emas (CUSTOM xabarlar dinamik slug'ga
        ega) — sarlavha bevosita mos `BotMessageTemplate.title`dan olinadi."""
        template = BotMessageTemplate.objects.filter(slug=obj.slug).first()
        return template.title if template else obj.slug

    def validate(self, attrs):
        slug = attrs.get("slug", getattr(self.instance, "slug", None))
        if slug and not BotMessageTemplate.objects.filter(slug=slug).exists():
            raise serializers.ValidationError(
                {"slug": "Bu slug'ga mos bot xabari (Bot xabarlari konstruktoridagi qator) topilmadi."}
            )
        media_type = attrs.get("media_type", getattr(self.instance, "media_type", BotMedia.MediaType.VIDEO))
        video_shape = attrs.get("video_shape", getattr(self.instance, "video_shape", BotMedia.VideoShape.RECTANGLE))
        has_file = attrs.get("file") if "file" in attrs else getattr(self.instance, "file", None)
        has_url = attrs.get("video_url") if "video_url" in attrs else getattr(self.instance, "video_url", None)

        if not has_file and not has_url:
            raise serializers.ValidationError("Media fayl yuklang yoki tashqi URL kiriting.")

        if has_url and media_type != BotMedia.MediaType.VIDEO:
            raise serializers.ValidationError("Tashqi URL faqat video turi uchun ishlatiladi — audio/rasm fayl sifatida yuklanishi kerak.")

        if media_type == BotMedia.MediaType.VIDEO and video_shape == BotMedia.VideoShape.CIRCLE and not has_file:
            raise serializers.ValidationError(
                "Dumaloq video (video xabar) faqat yuklangan fayl uchun ishlaydi — tashqi URL bo'lishi mumkin emas."
            )
        return attrs


class BotLinkSerializer(serializers.ModelSerializer):
    key_display = serializers.CharField(source="get_key_display", read_only=True)

    class Meta:
        model = BotLink
        fields = ["id", "key", "key_display", "url", "updated_at"]


class BotMessageTemplateSerializer(serializers.ModelSerializer):
    """
    Bot konstruktori uchun: har bir xabar qatoriga mos keladigan TAHRIRLANADIGAN
    matn/sarlavha, shu slug'ga biriktirilgan media bilan birga (o'qish uchun —
    media hamon `/bot-media/{slug}/` orqali alohida boshqariladi).

    2-avlod dinamik voronka: `step_type='core'` qatorlar hamon kod bilan
    bog'langan (`slug`/`group` o'zgarmaydi), lekin `step_type='custom'`
    qatorlarni admin konstruktor orqali yaratishi, o'chirishi va (`group`
    o'zgartirish orqali) boshqa toifaga ko'chirishi mumkin — bu ViewSet
    darajasida (`create`/`destroy`) va shu yerdagi `validate()`da
    tekshiriladi.

    `is_locked=True` bo'lgan qatorlarni faqat superuser tahrirlay oladi.
    """

    group_display = serializers.CharField(source="get_group_display", read_only=True)
    step_type_display = serializers.CharField(source="get_step_type_display", read_only=True)
    trigger_event_display = serializers.CharField(source="get_trigger_event_display", read_only=True)
    media = serializers.SerializerMethodField()
    position_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = BotMessageTemplate
        fields = [
            "id", "slug", "group", "group_display", "step_type", "step_type_display",
            "is_active", "trigger_event", "trigger_event_display", "attempt_number",
            "title", "text", "default_text", "placeholders", "is_locked",
            "position", "position_locked", "media", "updated_at", "updated_by",
        ]
        read_only_fields = ["slug", "step_type", "default_text", "placeholders", "updated_at", "updated_by"]

    def get_media(self, obj):
        media = BotMedia.objects.filter(slug=obj.slug).first()
        return BotMediaSerializer(media).data if media else None

    def validate(self, attrs):
        request = self.context.get("request")
        instance = self.instance

        if instance and instance.is_locked and request and not request.user.is_superuser:
            raise serializers.ValidationError(
                "Bu xabar qulflangan (huquqiy/nozik matn) — faqat superuser tahrirlay oladi."
            )
        if (
            instance
            and "position" in attrs
            and attrs["position"] != instance.position
            and instance.position_locked
        ):
            raise serializers.ValidationError(
                "Bu guruh (eslatmalar) uchun kartochka pozitsiyasi qulflangan — "
                "faqat matn/sarlavha/media tahrirlanadi, tartib o'zgarmaydi."
            )
        if instance and instance.step_type == BotMessageTemplate.StepType.CORE and "group" in attrs and attrs["group"] != instance.group:
            raise serializers.ValidationError(
                "Bu tizim bosqichi (CORE) doimiy ravishda o'z toifasiga tegishli — uni boshqa toifaga o'tkazib bo'lmaydi."
            )

        # Yakuniy (attrs qo'llangandan keyingi) holatni model.clean() orqali tekshiramiz —
        # shu bilan model va API bir xil qoidaga amal qiladi (bitta joyda yozilgan).
        # `slug` va `step_type` — serializerda read_only (client bevosita o'zgartira
        # olmaydi), shuning uchun `attrs` ichida umuman bo'lmaydi. YANGI qator
        # (`instance is None`) uchun bu har doim `BotMessageViewSet.create()` orqali
        # keladi, u FAQAT CUSTOM qator yaratadi — shu sabab bu yerda ham fallback
        # CUSTOM bo'lishi kerak (avval CORE edi — shu sabab har bir yangi xabar
        # "CORE turidagi qator faqat kod ichida mavjud slug'larga tegishli" xatosi
        # bilan rad etilardi, chunki bo'sh slug CORE sifatida tekshirilardi).
        default_step_type = (
            getattr(instance, "step_type", None) if instance else BotMessageTemplate.StepType.CUSTOM
        ) or BotMessageTemplate.StepType.CORE
        merged = {
            "slug": attrs.get("slug", getattr(instance, "slug", "")),
            "group": attrs.get("group", getattr(instance, "group", None)),
            "step_type": attrs.get("step_type", default_step_type),
            "trigger_event": attrs.get("trigger_event", getattr(instance, "trigger_event", None)),
            "attempt_number": attrs.get("attempt_number", getattr(instance, "attempt_number", None)),
        }
        probe = BotMessageTemplate(**merged)
        try:
            probe.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

        if merged["group"] == BotMessageTemplate.CASCADE_GROUP and merged["trigger_event"] == "attempt":
            from subscriptions.renewal_config import max_attempts

            limit = max_attempts()
            if merged["attempt_number"] and merged["attempt_number"] > limit:
                raise serializers.ValidationError(
                    {
                        "attempt_number": (
                            f"Joriy avto-to'lov sozlamalarida jami urinishlar soni {limit} ta "
                            f"(qarang: Avto to'lov vaqt sozlamalari) — {merged['attempt_number']}-urinishga "
                            f"xabar biriktirib bo'lmaydi."
                        )
                    }
                )
        return attrs

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user
        return super().update(instance, validated_data)


class FunnelCategorySettingsSerializer(serializers.ModelSerializer):
    """
    Voronka konstruktoridagi kategoriya (bo'lim) larning EKRANDA ko'rsatilish
    tartibi. `dependencies`/`blocked_by` — front-end uchun tayyor ma'lumot:
    qaysi kategoriyalar bundan OLDIN turishi SHART (shu sabab ularni bu
    kategoriyadan pastga sudrab bo'lmaydi — UI shuni oldindan bloklaydi).
    """

    category_display = serializers.CharField(source="get_category_display", read_only=True)
    dependencies = serializers.SerializerMethodField()

    class Meta:
        model = FunnelCategorySettings
        fields = ["id", "category", "category_display", "sort_order", "dependencies", "updated_at", "updated_by"]
        read_only_fields = ["updated_at", "updated_by"]

    def get_dependencies(self, obj):
        from cms.funnel import CATEGORY_DEPENDENCIES

        return CATEGORY_DEPENDENCIES.get(obj.category, [])


class ChannelSettingsSerializer(serializers.ModelSerializer):
    """
    Yopiq kanaldan avtomatik chiqarib yuborish uchun texnik sozlama (singleton).
    `channel_chat_id` — kanal havolasi EMAS, raqamli chat ID (masalan -1001234567890).
    """

    class Meta:
        model = ChannelSettings
        fields = ["id", "channel_chat_id", "auto_kick_on_expiry", "updated_at"]
        read_only_fields = ["updated_at"]