# JOYLASHTIRISH MANZILI: ACADEMY_BACK/admin_api/viewsets.py

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
import django_filters as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.models import TelegramUser
from subscriptions.models import (
    SubscriptionPlan, PaymentCard, Subscription, Payment, PendingCheckout,
    SubscriptionRenewalCycle, RenewalAttempt, PaymentReminderLog, RenewalRetryStage,
)
from gifts.models import GiftMonth, UserGiftProgress, UserGiftClaim
from content.models import (
    Material, ContentCategory, Content, ContentLike, CommunityCategory, CommunityContent,
)
from cms.models import BotMedia, BotLink, BotMessageTemplate, FunnelCategorySettings
from growth.models import ReferralLink
from broadcast.models import Broadcast, BroadcastRecipient
from broadcast.tasks import send_broadcast_task, dispatch_scheduled_broadcast

from .base import AdminModelViewSet
from .permissions import IsSuperUserForWrite
from . import serializers as s


# ---------------------------------------------------------------------------
# Xodimlar (Django auth.User)
# ---------------------------------------------------------------------------
class AdminStaffUserViewSet(AdminModelViewSet):
    """
    Admin panelga kiradigan xodimlar ro'yxati. O'qish — har qanday is_staff
    xodim uchun; yozish (create/update/delete) — faqat superuser uchun
    (`IsSuperUserForWrite`, ADMIN_API.md dagi xavfsizlik eslatmasiga muvofiq).
    """

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = s.AdminStaffUserSerializer
    permission_classes = [IsSuperUserForWrite]
    filterset_fields = ["is_staff", "is_superuser", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_fields = ["date_joined", "last_login", "username"]


# ---------------------------------------------------------------------------
# Mijozlar (TelegramUser)
# ---------------------------------------------------------------------------
class TelegramUserFilterSet(filters.FilterSet):
    # Obuna holati (Subscription.status) TelegramUser'da to'g'ridan-to'g'ri maydon emas —
    # `subscription` OneToOne orqali map qilinadi.
    subscription_status = filters.CharFilter(field_name="subscription__status")
    # Qidiruv (`search_fields`) allaqachon telefon bo'yicha ham ishlaydi, lekin admin panelda
    # alohida, aniq "faqat telefon" filtri so'ralgani uchun qo'shimcha maydon sifatida beriladi.
    phone_number = filters.CharFilter(field_name="phone_number", lookup_expr="icontains")
    # "Daraja" — mijoz uzluksiz necha oydan beri to'lov qilib kelayotgani
    # (gifts.UserGiftProgress.current_streak_months). To'lovda uzilish bo'lsa 0'ga tushadi
    # (qarang: UserGiftProgress.reset_streak). Bu yerda aynan shu raqam bo'yicha aniq filtr —
    # GiftMonth'dagi tier nomlariga bog'liq emas (u faqat ko'rsatish uchun, serializer'da).
    current_streak_months = filters.NumberFilter(method="filter_current_streak_months")

    class Meta:
        model = TelegramUser
        fields = ["registration_step", "is_blocked_bot", "subscription_status", "phone_number", "current_streak_months"]

    def filter_current_streak_months(self, queryset, name, value):
        try:
            streak = int(value)
        except (TypeError, ValueError):
            return queryset
        if streak <= 0:
            # Progress obyekti umuman yo'q mijozlar ham "0 oy" hisoblanadi.
            return queryset.filter(
                Q(gift_progress__isnull=True) | Q(gift_progress__current_streak_months=0)
            )
        return queryset.filter(gift_progress__current_streak_months=streak)


class TelegramUserViewSet(AdminModelViewSet):
    queryset = TelegramUser.objects.select_related(
        "subscription", "subscription__plan", "gift_progress",
    ).all()
    serializer_class = s.TelegramUserSerializer
    filterset_class = TelegramUserFilterSet
    search_fields = ["full_name", "username", "telegram_id", "phone_number"]
    ordering_fields = ["created_at", "updated_at", "full_name"]

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        user = self.get_object()
        user.is_blocked_bot = True
        user.save(update_fields=["is_blocked_bot"])
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        user = self.get_object()
        user.is_blocked_bot = False
        user.save(update_fields=["is_blocked_bot"])
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """
        Bitta mijoz haqida to'liq ko'rinish: obuna, so'nggi to'lovlar,
        sovg'a progressi va olingan sovg'alar — admin alohida 4 ta so'rov
        yubormasdan bitta joydan ko'rishi uchun.
        """
        user = self.get_object()

        subscription = getattr(user, "subscription", None)
        subscription_data = s.SubscriptionSerializer(subscription).data if subscription else None

        payments_qs = Payment.objects.filter(subscription__user=user).order_by("-created_at")[:10]
        payments_data = s.PaymentSerializer(payments_qs, many=True).data

        gift_progress = getattr(user, "gift_progress", None)
        gift_progress_data = s.UserGiftProgressSerializer(gift_progress).data if gift_progress else None

        gift_claims_qs = UserGiftClaim.objects.filter(user=user).select_related("gift_month").order_by("-claimed_at")
        gift_claims_data = s.UserGiftClaimSerializer(gift_claims_qs, many=True).data

        return Response({
            "user": self.get_serializer(user).data,
            "subscription": subscription_data,
            "recent_payments": payments_data,
            "gift_progress": gift_progress_data,
            "gift_claims": gift_claims_data,
        })


# ---------------------------------------------------------------------------
# Obuna tariflari / kartalar / obunalar / to'lovlar
# ---------------------------------------------------------------------------
class SubscriptionPlanViewSet(AdminModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = s.SubscriptionPlanSerializer
    filterset_fields = ["is_active"]
    search_fields = ["title"]
    ordering_fields = ["position", "price_uzs", "price_usd", "duration_months"]


class PaymentCardViewSet(AdminModelViewSet):
    queryset = PaymentCard.objects.select_related("user").all()
    serializer_class = s.PaymentCardSerializer
    filterset_fields = ["is_primary", "user"]
    search_fields = ["masked_pan", "user__full_name", "user__telegram_id"]
    ordering_fields = ["created_at"]


class SubscriptionViewSet(AdminModelViewSet):
    queryset = Subscription.objects.select_related("user", "plan", "card").all()
    serializer_class = s.SubscriptionSerializer
    filterset_fields = ["status", "provider", "auto_renew", "plan", "user"]
    search_fields = ["user__full_name", "user__username", "user__telegram_id", "tribute_external_id"]
    ordering_fields = ["next_payment_date", "created_at", "updated_at", "started_at"]

    @action(detail=True, methods=["post"], url_path="cancel-auto-renew")
    def cancel_auto_renew(self, request, pk=None):
        subscription = self.get_object()
        subscription.auto_renew = False
        subscription.save(update_fields=["auto_renew"])
        return Response(self.get_serializer(subscription).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        """
        Bekor qilingan/tugagan obunani qayta faollashtiradi (masalan mijoz
        qo'lda to'lov qilgandan keyin admin tasdiqlaydi). next_payment_date
        so'rov tanasida berilishi mumkin, aks holda o'zgarmaydi.
        """
        subscription = self.get_object()
        subscription.status = Subscription.Status.ACTIVE
        subscription.auto_renew = True
        next_payment_date = request.data.get("next_payment_date")
        update_fields = ["status", "auto_renew"]
        if next_payment_date:
            subscription.next_payment_date = next_payment_date
            update_fields.append("next_payment_date")
        subscription.save(update_fields=update_fields)
        return Response(self.get_serializer(subscription).data)


class PaymentFilterSet(filters.FilterSet):
    # Payment'da to'g'ridan-to'g'ri "user" maydoni yo'q (faqat subscription orqali) —
    # lekin admin frontend mijoz sahifasida har doim `?user=<id>` yuboradi, shu sababli
    # bu yerda mos keladigan haqiqiy yo'lga (subscription__user) map qilinadi.
    user = filters.NumberFilter(field_name="subscription__user_id")

    class Meta:
        model = Payment
        fields = ["status", "provider", "currency", "is_recurring_charge", "user"]


class PaymentViewSet(AdminModelViewSet):
    queryset = Payment.objects.select_related("subscription", "subscription__user").all()
    serializer_class = s.PaymentSerializer
    filterset_class = PaymentFilterSet
    search_fields = ["external_transaction_id", "subscription__user__full_name", "subscription__user__telegram_id"]
    ordering_fields = ["created_at", "paid_at", "amount"]


class PendingCheckoutViewSet(AdminModelViewSet):
    queryset = PendingCheckout.objects.select_related("user", "plan").all()
    serializer_class = s.PendingCheckoutSerializer
    filterset_fields = ["provider", "purpose", "is_used", "user"]
    search_fields = ["checkout_uuid", "user__full_name", "user__telegram_id"]
    ordering_fields = ["created_at", "expires_at"]


class SubscriptionRenewalCycleViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Faqat GET/PATCH — audit maqsadida, yaratish/o'chirish tizim tomonidan avtomatik boshqariladi."""

    queryset = SubscriptionRenewalCycle.objects.select_related("subscription", "subscription__user").prefetch_related("attempts").all()
    serializer_class = s.SubscriptionRenewalCycleSerializer
    permission_classes = AdminModelViewSet.permission_classes
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = AdminModelViewSet.pagination_class
    filter_backends = AdminModelViewSet.filter_backends
    filterset_fields = ["status", "subscription"]
    search_fields = ["subscription__user__full_name", "subscription__user__telegram_id"]
    ordering_fields = ["due_date", "created_at", "next_attempt_at"]


class RenewalAttemptFilterSet(filters.FilterSet):
    # RenewalAttempt'da to'g'ridan-to'g'ri "user" maydoni yo'q (faqat cycle -> subscription
    # orqali) — lekin admin frontend mijoz sahifasida har doim `?user=<id>` yuboradi, shu
    # sababli bu yerda mos keladigan haqiqiy yo'lga (cycle__subscription__user) map qilinadi.
    user = filters.NumberFilter(field_name="cycle__subscription__user_id")
    # "To'lov yechishga urinilgan mijozlar" jadvali uchun: sana oralig'i (sanadan/sanagacha)
    # va mijoz telefon raqami bo'yicha filtrlar.
    phone_number = filters.CharFilter(field_name="cycle__subscription__user__phone_number", lookup_expr="icontains")
    date_from = filters.DateFilter(field_name="attempted_at", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="attempted_at", lookup_expr="date__lte")

    class Meta:
        model = RenewalAttempt
        fields = ["result", "cycle", "user", "phone_number", "date_from", "date_to"]


class RenewalAttemptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Faqat GET — audit jurnali, tahrirlanmaydi."""

    queryset = RenewalAttempt.objects.select_related("cycle", "cycle__subscription__user").all()
    serializer_class = s.RenewalAttemptSerializer
    permission_classes = AdminModelViewSet.permission_classes
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = AdminModelViewSet.pagination_class
    filter_backends = AdminModelViewSet.filter_backends
    filterset_class = RenewalAttemptFilterSet
    ordering_fields = ["attempted_at", "attempt_number"]


class PaymentReminderLogFilterSet(filters.FilterSet):
    # PaymentReminderLog'da to'g'ridan-to'g'ri "user" maydoni yo'q (faqat subscription
    # orqali) — mijoz sahifasidagi `?user=<id>` so'rovi shu yerda mos yo'lga map qilinadi.
    user = filters.NumberFilter(field_name="subscription__user_id")

    class Meta:
        model = PaymentReminderLog
        fields = ["reminder_type", "subscription", "user"]


class PaymentReminderLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Faqat GET — eslatmalar dedupe jurnali."""

    queryset = PaymentReminderLog.objects.select_related("subscription", "subscription__user").all()
    serializer_class = s.PaymentReminderLogSerializer
    permission_classes = AdminModelViewSet.permission_classes
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = AdminModelViewSet.pagination_class
    filter_backends = AdminModelViewSet.filter_backends
    filterset_class = PaymentReminderLogFilterSet
    ordering_fields = ["sent_at", "due_date"]


class RenewalRetryStageViewSet(
    mixins.ListModelMixin, mixins.UpdateModelMixin, mixins.CreateModelMixin,
    mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """
    Avto-to'lov qayta urinish bosqichlari — TO'LIQ DINAMIK konstruktor.

    - `list`: joriy barcha bosqichlarni (1-urinishdan boshlab) tartib bilan qaytaradi,
      bazada birorta ham qator bo'lmasa avtomatik zavod qiymatlari bilan urug'laydi.
    - `create`: YANGI bosqich (keyingi urinish) qo'shadi — `attempt_number` avtomatik
      (oxirgi + 1), body faqat `{"wait_hours": 12}` (ixtiyoriy, standart 24). Shu bilan
      birga, agar shu urinishga hali xabar biriktirilmagan bo'lsa, "Bot xabarlari"
      konstruktorida (`renewal_fail_cascade` guruhi) mos CUSTOM qator ham AVTOMATIK
      yaratiladi — admin darhol o'sha yerga o'tib matn yoza oladi.
    - `partial_update`/`update`: faqat `wait_hours` tahrirlanadi (`attempt_number`
      read-only — tartib buzilmasligi uchun).
    - `destroy`: FAQAT eng oxirgi (eng katta raqamli) bosqichni o'chirish mumkin —
      aks holda urinish raqamlari orasida bo'shliq paydo bo'lib, kaskad chalkashib
      ketishi mumkin. Kamida bitta bosqich (jami kamida 2 urinish) saqlanib qolishi shart.
    """

    queryset = RenewalRetryStage.objects.all()
    serializer_class = s.RenewalRetryStageSerializer
    permission_classes = [IsSuperUserForWrite]
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = None
    ordering_fields = ["attempt_number"]

    def list(self, request, *args, **kwargs):
        RenewalRetryStage.ensure_seeded()
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        from subscriptions.renewal_config import MAX_RETRY_STAGES

        RenewalRetryStage.ensure_seeded()
        last = RenewalRetryStage.objects.order_by("-attempt_number").first()
        next_attempt = (last.attempt_number if last else 0) + 1
        if next_attempt > MAX_RETRY_STAGES:
            return Response(
                {"detail": f"Qayta urinish bosqichlari soni {MAX_RETRY_STAGES} tadan oshmasligi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_hours = request.data.get("wait_hours", 24)
        try:
            wait_hours = int(raw_hours)
        except (TypeError, ValueError):
            return Response({"wait_hours": "Butun son bo'lishi kerak."}, status=status.HTTP_400_BAD_REQUEST)
        from subscriptions.renewal_config import MIN_RETRY_HOURS, MAX_RETRY_HOURS

        if not (MIN_RETRY_HOURS <= wait_hours <= MAX_RETRY_HOURS):
            return Response(
                {"wait_hours": f"Kutish vaqti {MIN_RETRY_HOURS}-{MAX_RETRY_HOURS} soat oralig'ida bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stage = RenewalRetryStage.objects.create(
            attempt_number=next_attempt,
            wait_hours=wait_hours,
            updated_by=request.user if request.user.is_authenticated else None,
        )

        # Shu urinishga hali xabar biriktirilmagan bo'lsa — Bot xabarlari
        # konstruktorida joy avtomatik ochiladi, admin faqat matnni yozadi.
        already_has_message = BotMessageTemplate.objects.filter(
            group=BotMessageTemplate.CASCADE_GROUP, trigger_event="attempt", attempt_number=next_attempt,
        ).exists()
        if not already_has_message:
            BotMessageTemplate.objects.create(
                group=BotMessageTemplate.CASCADE_GROUP,
                step_type=BotMessageTemplate.StepType.CUSTOM,
                trigger_event="attempt",
                attempt_number=next_attempt,
                title=f"To'lov yechilmadi — {next_attempt}-urinish",
                text=(
                    f"⚠️ Keyingi oy uchun to'lovingiz amalga oshmadi ({next_attempt}-urinish)\n\n"
                    "📌 Tarif: {tarif_name}\n💰 Narxi: {amount} so'm\n❌ Sababi: {error_reason}\n\n"
                    "Bu matnni admin panelda \"Bot xabarlari\" bo'limida o'zingizga moslab tahrirlang."
                ),
                default_text="",
                is_active=True,
                position=0,
                updated_by=request.user if request.user.is_authenticated else None,
            )

        return Response(self.get_serializer(stage).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        last = RenewalRetryStage.objects.order_by("-attempt_number").first()
        if not last or instance.attempt_number != last.attempt_number:
            return Response(
                {"detail": "Faqat ENG OXIRGI qayta urinish bosqichini o'chirish mumkin — aks holda urinish raqamlari orasida bo'shliq qoladi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if RenewalRetryStage.objects.count() <= 1:
            return Response(
                {"detail": "Kamida bitta qayta urinish bosqichi saqlanib qolishi shart (jami kamida 2 urinish)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user if self.request.user.is_authenticated else None)


# ---------------------------------------------------------------------------
# Sovg'alar
# ---------------------------------------------------------------------------
class GiftMonthViewSet(AdminModelViewSet):
    queryset = GiftMonth.objects.all()
    serializer_class = s.GiftMonthSerializer
    filterset_fields = ["is_active"]
    search_fields = ["tier_name", "gift_name"]
    ordering_fields = ["month_number"]


class UserGiftProgressViewSet(AdminModelViewSet):
    queryset = UserGiftProgress.objects.select_related("user").all()
    serializer_class = s.UserGiftProgressSerializer
    filterset_fields = ["current_streak_months"]
    search_fields = ["user__full_name", "user__telegram_id"]
    ordering_fields = ["current_streak_months", "highest_streak_months", "updated_at"]


class UserGiftClaimViewSet(AdminModelViewSet):
    queryset = UserGiftClaim.objects.select_related("user", "gift_month").all()
    serializer_class = s.UserGiftClaimSerializer
    filterset_fields = ["gift_month", "user"]
    search_fields = ["user__full_name", "user__telegram_id", "gift_month__gift_name"]
    ordering_fields = ["claimed_at"]


# ---------------------------------------------------------------------------
# Kontent / Materiallar / Jamiyat
# ---------------------------------------------------------------------------
class MaterialViewSet(AdminModelViewSet):
    queryset = Material.objects.all()
    serializer_class = s.MaterialSerializer
    filterset_fields = ["is_active"]
    search_fields = ["title"]
    ordering_fields = ["position"]


class ContentCategoryFilterSet(filters.FilterSet):
    parent = filters.NumberFilter(field_name="parent_id")
    is_root = filters.BooleanFilter(field_name="parent", lookup_expr="isnull")

    class Meta:
        model = ContentCategory
        fields = ["is_active", "parent", "is_root"]


class ContentCategoryViewSet(AdminModelViewSet):
    queryset = ContentCategory.objects.select_related("parent").all()
    serializer_class = s.ContentCategorySerializer
    filterset_class = ContentCategoryFilterSet
    search_fields = ["name"]
    ordering_fields = ["position"]


class ContentFilterSet(filters.FilterSet):
    # Kontent nomi bo'yicha aniq filtr (qidiruv maydoni description'ni ham qamrab oladi,
    # bu esa faqat sarlavha bo'yicha filtrlash uchun).
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    # 1-daraja (TOP) kategoriya nomi — agar kontentning kategoriyasi ichki (child) bo'lsa
    # uning ota-kategoriyasi, agar o'zi TOP bo'lsa o'zining nomi tekshiriladi.
    first_category = filters.CharFilter(method="filter_first_category")
    # 2-daraja (ichki/leaf) kategoriya nomi — kontent to'g'ridan-to'g'ri biriktirilgan kategoriya.
    second_category = filters.CharFilter(field_name="category__name", lookup_expr="icontains")

    class Meta:
        model = Content
        fields = ["category", "media_type", "is_active", "title", "first_category", "second_category"]

    def filter_first_category(self, queryset, name, value):
        # Kategoriyalar cheksiz chuqurlikda ichma-ich bo'lishi mumkin bo'lgani uchun
        # "birinchi/TOP daraja" nomini SQL orqali emas, har bir kategoriyaning haqiqiy
        # ildizigacha (get_root) Python darajasida yurib topamiz.
        matching_root_ids = {
            cat.id for cat in ContentCategory.objects.all()
            if value.lower() in cat.get_root().name.lower()
        }
        return queryset.filter(category_id__in=matching_root_ids)


class ContentViewSet(AdminModelViewSet):
    queryset = Content.objects.select_related("category", "category__parent").all()
    serializer_class = s.ContentSerializer
    filterset_class = ContentFilterSet
    search_fields = ["title", "description"]
    ordering_fields = ["position", "published_date"]


class ContentLikeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Faqat GET/DELETE — like'lar admin panelda yaratilmaydi, faqat kuzatiladi/o'chiriladi."""

    queryset = ContentLike.objects.select_related("user", "content").all()
    serializer_class = s.ContentLikeSerializer
    permission_classes = AdminModelViewSet.permission_classes
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = AdminModelViewSet.pagination_class
    filter_backends = AdminModelViewSet.filter_backends
    filterset_fields = ["content", "user"]
    ordering_fields = ["created_at"]


class CommunityCategoryViewSet(AdminModelViewSet):
    queryset = CommunityCategory.objects.all()
    serializer_class = s.CommunityCategorySerializer
    filterset_fields = ["is_active"]
    search_fields = ["name"]
    ordering_fields = ["position"]


class CommunityContentViewSet(AdminModelViewSet):
    queryset = CommunityContent.objects.select_related("category").all()
    serializer_class = s.CommunityContentSerializer
    filterset_fields = ["category", "is_active"]
    search_fields = ["title", "description"]
    ordering_fields = ["position"]


# ---------------------------------------------------------------------------
# Bot xabarlari konstruktori / medialari / havolalari — 2-avlod DINAMIK voronka
#
# `group` (kategoriya) hamon kod tomonidan (handlerlar/celery tasklar)
# belgilangan chaqiruv nuqtasi — admin panel orqali yangi kategoriya
# qo'shilmaydi/o'chirilmaydi. LEKIN har bir kategoriya ICHIDA endi qatorlar
# to'liq dinamik: `step_type=core` qatorlar (kod ichida haqiqiy chaqiriladigan
# nuqtalar) o'chirilmaydi, lekin `step_type=custom` qatorlarni admin
# konstruktor orqali yaratishi va o'chirishi mumkin — bular kodga bog'liq
# bo'lmagan qo'shimcha xabarlar. Qarang: `cms/models.py`, `cms/funnel.py`.
# ---------------------------------------------------------------------------
class BotMessageViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
    mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """
    Bot xabarlari konstruktori: ro'yxat/detal/tahrirlash/yaratish/o'chirish.

    Yaratish (`create`) va o'chirish (`destroy`) FAQAT `step_type=custom`
    qatorlar uchun ishlaydi — CORE qatorlar (kod ichida haqiqiy chaqiriladigan
    nuqtalar) hamon o'zgarmas to'plam, na yaratiladi, na o'chiriladi.
    """

    queryset = BotMessageTemplate.objects.all()
    serializer_class = s.BotMessageTemplateSerializer
    permission_classes = AdminModelViewSet.permission_classes
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = AdminModelViewSet.pagination_class
    filter_backends = AdminModelViewSet.filter_backends
    filterset_fields = ["group", "is_locked", "step_type", "trigger_event"]
    search_fields = ["slug", "title", "text"]
    ordering_fields = ["group", "position", "slug", "updated_at", "attempt_number"]
    lookup_field = "slug"

    def create(self, request, *args, **kwargs):
        """
        Yangi CUSTOM xabar qo'shish. `step_type` majburiy emas — har doim
        serverda `custom` deb belgilanadi (client CORE qator yarata olmaydi).
        `group` majburiy — qaysi kategoriyaga tegishli ekanini bildiradi.
        """
        # `slug` va `step_type` — serializerda read_only, shuning uchun ularni
        # `request.data` ichida o'zgartirish hech narsaga ta'sir qilmaydi (DRF
        # ularni to_internal_value()da butunlay e'tiborsiz qoldiradi). Haqiqiy
        # majburlash faqat `.save()`ga to'g'ridan-to'g'ri kwarg sifatida uzatish
        # orqali ishlaydi — xuddi `updated_by`/`default_text` kabi.
        data = dict(request.data)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(
            updated_by=request.user if request.user.is_authenticated else None,
            default_text=data.get("text", ""),
            step_type=BotMessageTemplate.StepType.CUSTOM,
            slug="",  # model.save() avtomatik generatsiya qiladi (CUSTOM bo'lgani uchun)
        )
        # Guruh ichida oxiriga qo'shiladi (yoki kaskadda shu attempt/hodisa ichida oxiriga)
        siblings_qs = BotMessageTemplate.objects.filter(group=instance.group).exclude(pk=instance.pk)
        if instance.group == BotMessageTemplate.CASCADE_GROUP:
            siblings_qs = siblings_qs.filter(trigger_event=instance.trigger_event, attempt_number=instance.attempt_number)
        max_position = siblings_qs.order_by("-position").values_list("position", flat=True).first()
        instance.position = (max_position or 0) + 1
        instance.save(update_fields=["position"])
        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.step_type != BotMessageTemplate.StepType.CUSTOM:
            return Response(
                {"detail": "Bu tizim bosqichi (CORE) — o'chirib bo'lmaydi, faqat vaqtincha o'chirish (is_active=false) mumkin."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if instance.is_locked and not request.user.is_superuser:
            return Response(
                {"detail": "Bu xabar qulflangan — faqat superuser o'chira oladi."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def variables(self, request):
        """
        Berilgan kategoriya (`?category=payment`) uchun matn ichiga qo'shish
        mumkin bo'lgan dinamik o'zgaruvchilar ro'yxati — admin panel matn
        tahrirlash oynasidagi "+ O'zgaruvchi qo'shish" tanlagichini shu
        to'ldiradi.
        """
        from cms.funnel import available_variables

        category = request.query_params.get("category")
        if not category:
            return Response(
                {"detail": "'category' query-parametri majburiy (masalan ?category=payment)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"category": category, "variables": available_variables(category)})

    @action(detail=True, methods=["post"])
    def reset(self, request, slug=None):
        """Matnni va sarlavhani zavod sozlamasiga (`default_text`) qaytaradi."""
        template = self.get_object()
        if template.is_locked and not request.user.is_superuser:
            return Response(
                {"detail": "Bu xabar qulflangan — faqat superuser asliga qaytara oladi."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from cms.bot_texts import BOT_TEXTS

        original_title = BOT_TEXTS.get(slug, {}).get("title", template.title)
        template.text = template.default_text
        template.title = original_title
        template.updated_by = request.user
        template.save()
        return Response(self.get_serializer(template).data)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """
        Konstruktorda bitta guruh (lane) ichida kartochkalarni sudrab qo'yilgandan
        keyin, yakuniy tartibni bir martada saqlash uchun. Faqat BITTA guruh
        ichidagi slug'lar qabul qilinadi — guruhlar orasida ko'chirish yo'q
        (bu botning haqiqiy chaqiruv nuqtalarini chalkashtirib yuboradi).

        Body: {"group": "onboarding", "order": ["ask_name", "ask_phone", "phone_accepted"]}
        """
        group = request.data.get("group")
        order = request.data.get("order")
        if not group or not isinstance(order, list) or not order:
            return Response(
                {"detail": "'group' va bo'sh bo'lmagan 'order' (slug'lar ro'yxati) majburiy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        templates = list(BotMessageTemplate.objects.filter(group=group))
        if any(t.position_locked for t in templates):
            return Response(
                {"detail": "Bu guruh (avto-to'lov kaskadi) uchun kartochka pozitsiyasi qulflangan."},
                status=status.HTTP_403_FORBIDDEN,
            )

        by_slug = {t.slug: t for t in templates}
        if set(order) != set(by_slug):
            return Response(
                {"detail": "'order' ro'yxati ushbu guruhdagi barcha (va faqat o'sha) slug'larni o'z ichiga olishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for position, slug in enumerate(order):
            template = by_slug[slug]
            template.position = position
            template.updated_by = request.user if request.user.is_authenticated else None
            template.save(update_fields=["position", "updated_by"])

        return Response(self.get_serializer(templates, many=True).data)

    @action(detail=True, methods=["post"], url_path="test-send")
    def test_send(self, request, slug=None):
        """
        Joriy (saqlangan) matnni ko'rsatilgan Telegram chatiga sinov sifatida
        yuboradi — nashr qilishdan oldin ko'rish uchun. Placeholder'lar bo'lsa,
        haqiqiy qiymat o'rniga o'zining nomi bilan ko'rsatiladi (masalan
        `{tarif_name}` -> `[tarif_name]`), shuning uchun real foydalanuvchi/obuna
        ma'lumoti kerak emas.

        Shu slug'ga admin panel orqali media (rasm/video/audio) biriktirilgan bo'lsa,
        u ham haqiqiy botdagi kabi (`cms.services.asend_static`) yuboriladi — matn
        o'sha medianing caption'i sifatida ketadi (dumaloq video-xabar bundan mustasno,
        u caption qabul qilmaydi, shuning uchun matn undan keyin alohida yuboriladi).
        """
        import re

        template = self.get_object()
        telegram_id = request.data.get("telegram_id")
        if not telegram_id:
            return Response(
                {"detail": "telegram_id majburiy — sinov xabari yuboriladigan Telegram ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        preview_text = re.sub(r"\{(\w+)\}", r"[\1]", template.text)
        try:
            from cms.services import send_raw_with_media

            send_raw_with_media(template.slug, int(telegram_id), preview_text)
        except Exception as exc:  # noqa: BLE001
            return Response({"detail": f"Yuborishda xatolik: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Sinov xabari yuborildi."})


class FunnelCategoryViewSet(
    mixins.ListModelMixin, viewsets.GenericViewSet,
):
    """
    Voronka sahifasidagi kategoriya (bo'lim) larning EKRANDA ko'rsatilish
    tartibi. Admin bo'limlarni (masalan "Asosiy menyu"ni "Taklif va
    to'lov"dan yuqoriroq) sudrab qayta tartiblashi mumkin — lekin faqat
    `cms.funnel.CATEGORY_DEPENDENCIES` bog'liqligini buzmaydigan tarzda.
    """

    queryset = FunnelCategorySettings.objects.all()
    serializer_class = s.FunnelCategorySettingsSerializer
    permission_classes = AdminModelViewSet.permission_classes
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = None

    def list(self, request, *args, **kwargs):
        FunnelCategorySettings.ensure_seeded()
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """
        Butun voronka sahifasidagi kategoriyalar tartibini bir martada
        saqlaydi. Body: {"order": ["onboarding", "payment", "main_menu", ...]}

        Agar tartib bog'liqlik qoidasini buzsa (masalan "main_menu"
        "onboarding"dan OLDINGA qo'yilsa), `400` bilan aniq sababi
        tushuntiriladi va HECH NARSA saqlanmaydi.
        """
        from cms.funnel import validate_category_order

        order = request.data.get("order")
        if not isinstance(order, list) or not order:
            return Response({"detail": "Bo'sh bo'lmagan 'order' (kategoriya kalitlari ro'yxati) majburiy."}, status=status.HTTP_400_BAD_REQUEST)

        FunnelCategorySettings.ensure_seeded()
        existing = set(FunnelCategorySettings.objects.values_list("category", flat=True))
        if set(order) != existing:
            return Response(
                {"detail": "'order' ro'yxati barcha (va faqat o'sha) mavjud kategoriyalarni o'z ichiga olishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        error = validate_category_order(order)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        by_category = {c.category: c for c in FunnelCategorySettings.objects.all()}
        for index, category in enumerate(order):
            row = by_category[category]
            row.sort_order = index
            row.updated_by = request.user if request.user.is_authenticated else None
            row.save(update_fields=["sort_order", "updated_by"])

        return Response(self.get_serializer(FunnelCategorySettings.objects.all(), many=True).data)


class BotMediaViewSet(AdminModelViewSet):
    """Bot xabarlariga (istalgan statik slugga) biriktiriladigan media — CRUD, `slug` orqali."""

    queryset = BotMedia.objects.all()
    serializer_class = s.BotMediaSerializer
    lookup_field = "slug"
    search_fields = ["slug"]
    ordering_fields = ["updated_at", "slug"]


class BotLinkViewSet(AdminModelViewSet):
    queryset = BotLink.objects.all()
    serializer_class = s.BotLinkSerializer
    filterset_fields = ["key"]
    search_fields = ["key", "url"]
    ordering_fields = ["updated_at"]


# ---------------------------------------------------------------------------
# Qabul va reklama kampaniyalari (referal havolalar)
# ---------------------------------------------------------------------------
class ReferralLinkViewSet(AdminModelViewSet):
    """
    Reklama kampaniyalari uchun referal havolalar (`t.me/<bot>?start=<code>`).
    `leads_count`/`sales_count` faqat botning o'zi tomonidan (foydalanuvchi /start
    bosganda va birinchi to'lov qilganda) oshiriladi — admin panel orqali qo'lda
    o'zgartirilmaydi (serializer'da read-only).
    """

    queryset = ReferralLink.objects.all()
    serializer_class = s.ReferralLinkSerializer
    filterset_fields = ["is_active"]
    search_fields = ["code", "label"]
    ordering_fields = ["created_at", "leads_count", "sales_count"]


# ---------------------------------------------------------------------------
# E'lonlar (Broadcast)
# ---------------------------------------------------------------------------
class BroadcastViewSet(AdminModelViewSet):
    queryset = Broadcast.objects.select_related("target_plan").all()
    serializer_class = s.BroadcastSerializer
    filterset_fields = ["status", "target_type", "target_plan"]
    search_fields = ["title", "text"]
    ordering_fields = ["created_at", "sent_at"]

    def perform_create(self, serializer):
        broadcast = serializer.save()
        self._sync_schedule(broadcast)

    def perform_update(self, serializer):
        broadcast = serializer.save()
        self._sync_schedule(broadcast)

    def _sync_schedule(self, broadcast: Broadcast):
        """
        `scheduled_at` maydoni to'ldirilgan/o'zgartirilgan bo'lsa — Celery'ga `eta` bilan
        bir martalik vazifa qo'yiladi va holat SCHEDULED'ga o'tkaziladi.

        Bu QORALAMA/REJALASHTIRILGAN e'lonlar uchun ham, allaqachon YUBORILGAN yoki
        XATOLIK bilan tugagan e'lonlar uchun ham ishlaydi — ya'ni admin bir marta
        yuborilgan e'lonni qayta tahrirlab, yangi vaqtga rejalashtirsa, u QAYTA
        YUBORILADI. Bunday holda avvalgi yuborish natijalari (qabul qiluvchilar
        ro'yxati, hisoblagichlar) tozalanadi — chunki bu endi yangi yuborish siklidir.
        QUEUED/SENDING holatidagi (hozir jarayonda bo'lgan) e'lonlarga tegilmaydi.
        """
        if broadcast.status in (Broadcast.Status.QUEUED, Broadcast.Status.SENDING):
            return
        if broadcast.scheduled_at:
            if broadcast.status in (Broadcast.Status.SENT, Broadcast.Status.FAILED):
                # Qayta yuborish — eski natijalarni tozalab, boshidan boshlaymiz.
                broadcast.recipients.all().delete()
                broadcast.total_recipients = 0
                broadcast.sent_count = 0
                broadcast.failed_count = 0
                broadcast.sent_at = None
                broadcast.status = Broadcast.Status.SCHEDULED
                broadcast.save(update_fields=[
                    "status", "total_recipients", "sent_count", "failed_count", "sent_at",
                ])
            elif broadcast.status != Broadcast.Status.SCHEDULED:
                broadcast.status = Broadcast.Status.SCHEDULED
                broadcast.save(update_fields=["status"])
            dispatch_scheduled_broadcast.apply_async(
                args=[broadcast.id, broadcast.scheduled_at.isoformat()],
                eta=broadcast.scheduled_at,
            )
        elif broadcast.status == Broadcast.Status.SCHEDULED:
            # scheduled_at tozalangan — rejadan chiqarib, qoralamaga qaytaramiz.
            # Eskirgan eta vazifasi `dispatch_scheduled_broadcast` ichidagi tekshiruv
            # tufayli o'zi hech narsa qilmaydi.
            broadcast.status = Broadcast.Status.DRAFT
            broadcast.save(update_fields=["status"])

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """
        E'lonni DARHOL yuborishga navbatga qo'yadi (haqiqiy yuborish Celery task orqali
        background da amalga oshadi — rate-limitga tushmaslik uchun). Agar e'lon
        rejalashtirilgan bo'lsa ham, bu tugma bosilsa kutmasdan darhol yuboriladi.
        """
        broadcast = self.get_object()
        if broadcast.status not in (Broadcast.Status.DRAFT, Broadcast.Status.SCHEDULED, Broadcast.Status.FAILED):
            return Response(
                {"detail": "Bu e'lon allaqachon navbatga qo'yilgan yoki yuborilgan. Qayta yuborish uchun \"Qayta yuborish\" tugmasidan foydalaning."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        broadcast.status = Broadcast.Status.QUEUED
        broadcast.save(update_fields=["status"])
        send_broadcast_task.delay(broadcast.id)
        return Response(self.get_serializer(broadcast).data)

    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        """
        Allaqachon YUBORILGAN (yoki xatolik bilan tugagan) e'lonni butunlay YANGI yuborish
        sikli sifatida DARHOL qayta yuboradi: avvalgi qabul qiluvchilar ro'yxati va
        hisoblagichlar tozalanadi, so'ng barcha auditoriyaga qaytadan yuboriladi.
        """
        broadcast = self.get_object()
        if broadcast.status in (Broadcast.Status.QUEUED, Broadcast.Status.SENDING):
            return Response(
                {"detail": "Bu e'lon hozir yuborilish jarayonida — kuting."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        broadcast.recipients.all().delete()
        broadcast.total_recipients = 0
        broadcast.sent_count = 0
        broadcast.failed_count = 0
        broadcast.sent_at = None
        broadcast.status = Broadcast.Status.QUEUED
        broadcast.save(update_fields=["status", "total_recipients", "sent_count", "failed_count", "sent_at"])
        send_broadcast_task.delay(broadcast.id)
        return Response(self.get_serializer(broadcast).data)

    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        """Shu e'lonning qabul qiluvchilari ro'yxati (sahifalab)."""
        broadcast = self.get_object()
        qs = broadcast.recipients.select_related("user").all()
        is_sent = request.query_params.get("is_sent")
        if is_sent is not None:
            qs = qs.filter(is_sent=is_sent.lower() in ("1", "true", "yes"))
        page = self.paginate_queryset(qs)
        serializer = s.BroadcastRecipientSerializer(page if page is not None else qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class BroadcastRecipientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Faqat GET — qabul qiluvchilar ro'yxati tizim tomonidan avtomatik to'ldiriladi."""

    queryset = BroadcastRecipient.objects.select_related("broadcast", "user").all()
    serializer_class = s.BroadcastRecipientSerializer
    permission_classes = AdminModelViewSet.permission_classes
    authentication_classes = AdminModelViewSet.authentication_classes
    pagination_class = AdminModelViewSet.pagination_class
    filter_backends = AdminModelViewSet.filter_backends
    filterset_fields = ["broadcast", "user", "is_sent"]
    ordering_fields = ["sent_at"]