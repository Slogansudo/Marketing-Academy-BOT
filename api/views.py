from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from gifts.models import GiftMonth, UserGiftClaim
from content.models import Material, ContentCategory, Content, ContentLike, CommunityCategory, CommunityContent
from subscriptions.models import Subscription

from .serializers import (
    SubscriptionStatusSerializer, GiftMonthSerializer, MaterialSerializer,
    ContentCategorySerializer, ContentListSerializer, ContentDetailSerializer,
    CommunityCategorySerializer, CommunityContentSerializer,
)


class SubscriptionStatusView(APIView):
    """10-11-rasm: mini app tepasidagi 'SARDOR / Boshlovchi / 15.08.2026 gacha' bloki."""

    def get(self, request):
        user = request.user
        try:
            sub = user.subscription
        except Subscription.DoesNotExist:
            sub = None

        progress = getattr(user, "gift_progress", None)
        streak = progress.current_streak_months if progress else 0
        total_months = GiftMonth.objects.filter(is_active=True).count()
        current_tier = (
            GiftMonth.objects.filter(is_active=True, month_number=max(streak, 1)).first()
            or GiftMonth.objects.filter(is_active=True).order_by("month_number").first()
        )

        data = {
            "tier_name": current_tier.tier_name if current_tier else "Boshlovchi",
            "status_label": sub.get_status_display() if sub else "Obuna yo'q",
            "is_active": bool(sub and sub.status == Subscription.Status.ACTIVE),
            "next_payment_date": sub.next_payment_date if sub else None,
            "auto_renew": sub.auto_renew if sub else False,
            "masked_pan": sub.card.masked_pan if sub and sub.card else None,
            "current_streak_months": streak,
            "total_months_in_track": total_months,
        }
        return Response(SubscriptionStatusSerializer(data).data)


class GiftTrackView(APIView):
    """9-bosqich / 11-rasm: pastga surilib ko'rsatiladigan 1..N oylik sovg'alar tracki."""

    def get(self, request):
        user = request.user
        progress = getattr(user, "gift_progress", None)
        streak = progress.current_streak_months if progress else 0
        claimed = set(UserGiftClaim.objects.filter(user=user).values_list("gift_month__month_number", flat=True))

        gifts = GiftMonth.objects.filter(is_active=True).order_by("month_number")
        serializer = GiftMonthSerializer(
            gifts, many=True,
            context={"current_streak_months": streak, "claimed_month_numbers": claimed},
        )
        return Response(serializer.data)


class GiftClaimView(APIView):
    """
    'OLISH' tugmasi bosilganda chaqiriladi. Sovg'a ochiq bo'lsagina ruxsat beriladi,
    havolaga mijozning telefon raqami va telegram_id si avtomatik biriktiriladi
    (takroriy anketa to'ldirmasligi uchun — oldin olingan bo'lsa mavjud yozuv qaytariladi).
    """

    def post(self, request, month_number):
        user = request.user
        gift = get_object_or_404(GiftMonth, month_number=month_number, is_active=True)

        progress = getattr(user, "gift_progress", None)
        streak = progress.current_streak_months if progress else 0
        # 1-oy "Boshlovchi" darajasi har doim ochiq (GiftTrackView/is_unlocked bilan bir xil qoida) —
        # shuning uchun bu yerda ham max(streak, 1) ishlatiladi, aks holda streak=0 bo'lganda
        # frontendda "OLISH" tugmasi ochiq ko'rinadi-yu, backend uni 400 bilan rad etadi.
        if gift.month_number > max(streak, 1):
            return Response({"detail": "Bu oy uchun sovg'a hali ochilmagan"}, status=400)

        claim, _created = UserGiftClaim.objects.get_or_create(user=user, gift_month=gift)

        return Response({"claim_link": gift.claim_link, "already_claimed": not _created})


class MaterialListView(APIView):
    """10-bosqich: Materiallar sahifasi (12-13-rasm)."""

    def get(self, request):
        materials = Material.objects.filter(is_active=True)
        return Response(MaterialSerializer(materials, many=True).data)


class ContentCategoryListView(APIView):
    """12-bosqich: kategoriya kartochkalari (10, 15-rasm) — faqat TOP daражadagi (parent=None) kategoriyalar."""

    def get(self, request):
        categories = ContentCategory.objects.filter(is_active=True, parent__isnull=True)
        return Response(ContentCategorySerializer(categories, many=True).data)


class ContentSubcategoryListView(APIView):
    """
    Ichki kategoriyalar ro'yhati — mijoz `has_children=True` bo'lgan kategoriyani tanlaganda
    chaqiriladi (masalan 'Kurs' -> 'Aqlni rivojlantirish kurslari', 'Kitob o'qish kurslari', ...).
    """

    def get(self, request, category_id):
        get_object_or_404(ContentCategory, id=category_id, is_active=True)
        subcategories = ContentCategory.objects.filter(is_active=True, parent_id=category_id)
        return Response(ContentCategorySerializer(subcategories, many=True).data)


class ContentListView(APIView):
    """16-rasm: kategoriya ichidagi kontentlar ro'yhati."""

    def get(self, request, category_id):
        liked_ids = set(ContentLike.objects.filter(user=request.user).values_list("content_id", flat=True))
        contents = Content.objects.filter(category_id=category_id, is_active=True)
        serializer = ContentListSerializer(contents, many=True, context={"liked_content_ids": liked_ids})
        return Response(serializer.data)


class ContentDetailView(APIView):
    """17-rasm: bitta kontent detail (padrobiga o'xshash sahifa)."""

    def get(self, request, content_id):
        content = get_object_or_404(Content, id=content_id, is_active=True)
        liked_ids = set(ContentLike.objects.filter(user=request.user).values_list("content_id", flat=True))
        serializer = ContentDetailSerializer(content, context={"liked_content_ids": liked_ids})
        return Response(serializer.data)


class ContentLikeToggleView(APIView):
    """18-rasm: 'Saralangan' filter shu like modeliga qarab hosil bo'ladi."""

    def post(self, request, content_id):
        content = get_object_or_404(Content, id=content_id, is_active=True)
        like, created = ContentLike.objects.get_or_create(user=request.user, content=content)
        if not created:
            like.delete()
            return Response({"is_liked": False})
        return Response({"is_liked": True})


class LikedContentListView(APIView):
    def get(self, request):
        liked_ids = ContentLike.objects.filter(user=request.user).values_list("content_id", flat=True)
        contents = Content.objects.filter(id__in=liked_ids, is_active=True)
        serializer = ContentListSerializer(contents, many=True, context={"liked_content_ids": set(liked_ids)})
        return Response(serializer.data)


class CommunityCategoryListView(APIView):
    """19-rasm: Jamiyat sahifasi kategoriyalari."""

    def get(self, request):
        categories = CommunityCategory.objects.filter(is_active=True)
        return Response(CommunityCategorySerializer(categories, many=True).data)


class CommunityContentListView(APIView):
    def get(self, request, category_id):
        category = get_object_or_404(CommunityCategory, id=category_id, is_active=True)
        # Havolali kategoriya bo'lsa frontend `external_link` mavjudligini tekshirib
        # to'g'ridan-to'g'ri o'sha havolaga yo'naltiradi (ichkariga kirmasdan).
        items = CommunityContent.objects.filter(category=category, is_active=True)
        return Response({
            "category": CommunityCategorySerializer(category).data,
            "items": CommunityContentSerializer(items, many=True).data,
        })