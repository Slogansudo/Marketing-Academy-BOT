# JOYLASHTIRISH MANZILI: ACADEMY_BACK/admin_api/dashboard_views.py

import calendar
from datetime import datetime, timedelta

from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import TelegramUser
from subscriptions.models import (
    Subscription, Payment, SubscriptionPlan, PaymentCard,
    SubscriptionRenewalCycle, RenewalAttempt,
)
from gifts.models import UserGiftClaim
from content.models import Content, ContentLike
from broadcast.models import Broadcast

from .permissions import IsAdminStaff, IsSuperUserForWrite


class AdminDashboardView(APIView):
    """
    GET /api/admin/v1/dashboard/

    Admin panelning bosh sahifasi uchun bitta so'rovda barcha asosiy ko'rsatkichlar:
    foydalanuvchilar, obunalar, to'lovlar (bugun/shu oy), tariflar bo'yicha taqsimot,
    sovg'alar va e'lonlar holati. Admin har bir bo'limga alohida kirmasdan umumiy
    holatni darhol ko'rishi uchun.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]

    def get(self, request):
        now = timezone.now()
        today = now.date()
        month_start = today.replace(day=1)
        week_ago = today - timedelta(days=7)

        users_qs = TelegramUser.objects.all()
        subs_qs = Subscription.objects.all()
        payments_qs = Payment.objects.filter(status=Payment.Status.SUCCESS)

        users_stats = {
            "total": users_qs.count(),
            "registered": users_qs.filter(registration_step=TelegramUser.RegistrationStep.COMPLETED).count(),
            "blocked_bot": users_qs.filter(is_blocked_bot=True).count(),
            "new_last_7_days": users_qs.filter(created_at__date__gte=week_ago).count(),
        }

        subscriptions_stats = {
            "active": subs_qs.filter(status=Subscription.Status.ACTIVE).count(),
            "pending": subs_qs.filter(status=Subscription.Status.PENDING).count(),
            "cancelled": subs_qs.filter(status=Subscription.Status.CANCELLED).count(),
            "expired": subs_qs.filter(status=Subscription.Status.EXPIRED).count(),
            "auto_renew_on": subs_qs.filter(status=Subscription.Status.ACTIVE, auto_renew=True).count(),
            "by_plan": list(
                subs_qs.filter(status=Subscription.Status.ACTIVE)
                .values("plan__id", "plan__title")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
        }

        payments_stats = {
            "revenue_today_uzs": payments_qs.filter(currency="UZS", paid_at__date=today).aggregate(s=Sum("amount"))["s"] or 0,
            "revenue_month_uzs": payments_qs.filter(currency="UZS", paid_at__date__gte=month_start).aggregate(s=Sum("amount"))["s"] or 0,
            "revenue_today_usd": payments_qs.filter(currency="USD", paid_at__date=today).aggregate(s=Sum("amount"))["s"] or 0,
            "revenue_month_usd": payments_qs.filter(currency="USD", paid_at__date__gte=month_start).aggregate(s=Sum("amount"))["s"] or 0,
            "count_today": payments_qs.filter(paid_at__date=today).count(),
            "count_month": payments_qs.filter(paid_at__date__gte=month_start).count(),
            "failed_last_7_days": Payment.objects.filter(status=Payment.Status.FAILED, created_at__date__gte=week_ago).count(),
        }

        gifts_stats = {
            "total_claims": UserGiftClaim.objects.count(),
            "claims_last_7_days": UserGiftClaim.objects.filter(claimed_at__date__gte=week_ago).count(),
        }

        content_stats = {
            "total_content": Content.objects.count(),
            "active_content": Content.objects.filter(is_active=True).count(),
            "total_likes": ContentLike.objects.count(),
            "top_liked": list(
                Content.objects.annotate(likes_count=Count("likes"))
                .order_by("-likes_count")
                .values("id", "title", "likes_count")[:5]
            ),
        }

        broadcast_stats = {
            "draft": Broadcast.objects.filter(status=Broadcast.Status.DRAFT).count(),
            "queued_or_sending": Broadcast.objects.filter(
                Q(status=Broadcast.Status.QUEUED) | Q(status=Broadcast.Status.SENDING)
            ).count(),
            "scheduled": Broadcast.objects.filter(status=Broadcast.Status.SCHEDULED).count()
            if hasattr(Broadcast.Status, "SCHEDULED") else 0,
            "sent": Broadcast.objects.filter(status=Broadcast.Status.SENT).count(),
            "failed": Broadcast.objects.filter(status=Broadcast.Status.FAILED).count(),
        }

        # Mijozlar voronkasi (funnel): bot foydalanuvchisi -> ism/telefon -> karta -> to'lov.
        # "Jamiyat kanalida bor" deb hozircha faol obunachilar hisoblanadi — chunki yopiq kanalga
        # kirish huquqi faqat ACTIVE obunaga bog'liq (real Telegram a'zolar sonini olish uchun
        # kanalning chat_id'i sozlanishi va getChatMemberCount chaqirilishi kerak bo'ladi).
        funnel_stats = {
            "bot_users": users_qs.count(),
            "phone_provided": users_qs.exclude(Q(phone_number__isnull=True) | Q(phone_number="")).count(),
            "card_added": PaymentCard.objects.values("user_id").distinct().count(),
            "paid": payments_qs.values("subscription__user_id").distinct().count(),
            "community_channel_members": subs_qs.filter(status=Subscription.Status.ACTIVE).count(),
        }

        return Response({
            "generated_at": now,
            "users": users_stats,
            "subscriptions": subscriptions_stats,
            "payments": payments_stats,
            "gifts": gifts_stats,
            "content": content_stats,
            "broadcasts": broadcast_stats,
            "funnel": funnel_stats,
            "plans_total": SubscriptionPlan.objects.filter(is_active=True).count(),
        })


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


class AdminDashboardMonthlyAnalyticsView(APIView):
    """
    GET /api/admin/v1/dashboard/monthly/?months=12

    Oy bo'yicha: nechta YANGI obunachi qo'shildi (shu oyda birinchi marta ACTIVE bo'lgan),
    nechtasi oldingi oyni davom ettirdi (renewed — shu oyda muvaffaqiyatli 'is_recurring_charge'
    to'lovi bo'lgan obunalar), va retention rate — oldingi oy oxirida faol bo'lganlardan necha
    foizi shu oyda ham to'lov qilib obunasini uzaytirgani.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]

    def get(self, request):
        try:
            months_count = max(1, min(24, int(request.query_params.get("months", 12))))
        except (TypeError, ValueError):
            months_count = 12

        today = timezone.now().date()
        # Oxirgi N oyning har biri uchun (eng eskisidan boshlab) oy boshini hisoblaymiz.
        month_starts = []
        y, m = today.year, today.month
        for _ in range(months_count):
            month_starts.append(datetime(y, m, 1).date())
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        month_starts.reverse()

        payments_qs = Payment.objects.filter(status=Payment.Status.SUCCESS, paid_at__isnull=False)

        result = []
        for month_start in month_starts:
            last_day = calendar.monthrange(month_start.year, month_start.month)[1]
            month_end = month_start.replace(day=last_day)
            next_month_start = month_end + timedelta(days=1)

            month_payments = payments_qs.filter(paid_at__date__gte=month_start, paid_at__date__lte=month_end)

            # Yangi obunachilar: shu oyda birinchi (is_recurring_charge=False) to'lovni qilganlar.
            new_subscribers = (
                month_payments.filter(is_recurring_charge=False)
                .values("subscription__user_id").distinct().count()
            )
            # Uzaytirganlar: shu oyda takroriy (avto/qo'lda) to'lov qilganlar.
            renewed_subscribers = (
                month_payments.filter(is_recurring_charge=True)
                .values("subscription__user_id").distinct().count()
            )

            # Retention: oldingi oyda faol bo'lgan (shu oygacha to'lov qilgan) obunachilardan
            # nechtasi shu oyda ham kamida bitta muvaffaqiyatli to'lov qilgan.
            prev_month_end = month_start - timedelta(days=1)
            prev_month_start = prev_month_end.replace(day=1)
            active_prev_month = set(
                payments_qs.filter(paid_at__date__gte=prev_month_start, paid_at__date__lte=prev_month_end)
                .values_list("subscription__user_id", flat=True)
            )
            retained_this_month = set(
                month_payments.values_list("subscription__user_id", flat=True)
            )
            if active_prev_month:
                retention_rate = round(100 * len(active_prev_month & retained_this_month) / len(active_prev_month), 1)
            else:
                retention_rate = None

            result.append({
                "month": month_start.isoformat(),
                "label": month_start.strftime("%Y-%m"),
                "new_subscribers": new_subscribers,
                "renewed_subscribers": renewed_subscribers,
                "retention_rate": retention_rate,
                "cancelled": Subscription.objects.filter(
                    status=Subscription.Status.CANCELLED,
                    updated_at__date__gte=month_start,
                    updated_at__date__lte=min(month_end, today),
                ).count(),
            })

        return Response({"months": result})


class AdminDashboardDailyAnalyticsView(APIView):
    """
    GET /api/admin/v1/dashboard/daily/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&granularity=day|hour

    Kunlik (yoki soatlik) kesimda: nechta obuna boshlandi (yangi to'lov), nechta obuna
    bekor qilindi, muvaffaqiyatli va muvaffaqiyatsiz to'lovlar soni. `granularity=hour`
    berilsa, faqat bitta kun ichida (date_from) soat bo'yicha taqsimot qaytariladi —
    "sana bo'yicha ham, soat bo'yicha ham filtrlash" talabini qondiradi.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]

    def get(self, request):
        today = timezone.now().date()
        granularity = request.query_params.get("granularity", "day")
        date_to = _parse_date(request.query_params.get("date_to"), today)

        if granularity == "hour":
            # Soatlik rejim faqat bitta kun uchun (date_from yoki date_to, ustuvorlik date_from'da)
            day = _parse_date(request.query_params.get("date_from"), date_to)
            start_dt = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            end_dt = start_dt + timedelta(days=1)

            payments_success = (
                Payment.objects.filter(status=Payment.Status.SUCCESS, paid_at__gte=start_dt, paid_at__lt=end_dt)
                .annotate(bucket=TruncHour("paid_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
            )
            payments_failed = (
                Payment.objects.filter(status=Payment.Status.FAILED, created_at__gte=start_dt, created_at__lt=end_dt)
                .annotate(bucket=TruncHour("created_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
            )
            new_subs = (
                Subscription.objects.filter(started_at__gte=start_dt, started_at__lt=end_dt)
                .annotate(bucket=TruncHour("started_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
            )
            cancelled_subs = (
                Subscription.objects.filter(
                    status=Subscription.Status.CANCELLED, updated_at__gte=start_dt, updated_at__lt=end_dt
                )
                .annotate(bucket=TruncHour("updated_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
            )

            buckets = {h: {
                "bucket": start_dt.replace(hour=h, minute=0, second=0, microsecond=0).isoformat(),
                "label": f"{h:02d}:00",
                "new_subscriptions": 0, "cancelled_subscriptions": 0,
                "payments_success": 0, "payments_failed": 0,
            } for h in range(24)}

            for row in payments_success:
                buckets[row["bucket"].hour]["payments_success"] = row["count"]
            for row in payments_failed:
                buckets[row["bucket"].hour]["payments_failed"] = row["count"]
            for row in new_subs:
                buckets[row["bucket"].hour]["new_subscriptions"] = row["count"]
            for row in cancelled_subs:
                buckets[row["bucket"].hour]["cancelled_subscriptions"] = row["count"]

            return Response({"granularity": "hour", "date": day.isoformat(), "points": list(buckets.values())})

        # Kunlik rejim (sana oralig'i bo'yicha)
        date_from = _parse_date(request.query_params.get("date_from"), date_to - timedelta(days=29))
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        # Haddan tashqari katta oraliqni cheklab qo'yamiz (server yukini nazorat qilish uchun)
        if (date_to - date_from).days > 366:
            date_from = date_to - timedelta(days=366)

        start_dt = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(date_to, datetime.min.time())) + timedelta(days=1)

        payments_success = (
            Payment.objects.filter(status=Payment.Status.SUCCESS, paid_at__gte=start_dt, paid_at__lt=end_dt)
            .annotate(bucket=TruncDate("paid_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
        )
        payments_failed = (
            Payment.objects.filter(status=Payment.Status.FAILED, created_at__gte=start_dt, created_at__lt=end_dt)
            .annotate(bucket=TruncDate("created_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
        )
        new_subs = (
            Subscription.objects.filter(started_at__gte=start_dt, started_at__lt=end_dt)
            .annotate(bucket=TruncDate("started_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
        )
        cancelled_subs = (
            Subscription.objects.filter(
                status=Subscription.Status.CANCELLED, updated_at__gte=start_dt, updated_at__lt=end_dt
            )
            .annotate(bucket=TruncDate("updated_at")).values("bucket").annotate(count=Count("id")).order_by("bucket")
        )

        buckets = {}
        cursor = date_from
        while cursor <= date_to:
            buckets[cursor] = {
                "bucket": cursor.isoformat(), "label": cursor.strftime("%d.%m"),
                "new_subscriptions": 0, "cancelled_subscriptions": 0,
                "payments_success": 0, "payments_failed": 0,
            }
            cursor += timedelta(days=1)

        for row in payments_success:
            if row["bucket"] in buckets:
                buckets[row["bucket"]]["payments_success"] = row["count"]
        for row in payments_failed:
            if row["bucket"] in buckets:
                buckets[row["bucket"]]["payments_failed"] = row["count"]
        for row in new_subs:
            if row["bucket"] in buckets:
                buckets[row["bucket"]]["new_subscriptions"] = row["count"]
        for row in cancelled_subs:
            if row["bucket"] in buckets:
                buckets[row["bucket"]]["cancelled_subscriptions"] = row["count"]

        return Response({
            "granularity": "day",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "points": list(buckets.values()),
        })


class AdminAutoRenewalStatsView(APIView):
    """
    GET /api/admin/v1/dashboard/auto-renewal/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

    Avto to'lov (renewal) sahifasi uchun: (1) mijozlarning obunasi hozir avto to'lov
    bo'yicha qanday holatda turibdi (auto_renew yoqilgan/o'chirilgan, yangilash sikli
    qaysi bosqichda) — bular joriy holat, sana filtriga bog'liq emas; (2) berilgan sana
    oralig'ida (standart: bugun) qilingan urinishlar bo'yicha statistika — jami, muvaffaqiyatli,
    muvaffaqiyatsiz, urinilgan noyob mijozlar soni.

    Har bir alohida urinish yozuvlarining ro'yxati (pagination bilan) — RenewalAttempt
    endpointi (`/renewal-attempts/?date_from=&date_to=`) orqali alohida olinadi.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]

    def get(self, request):
        today = timezone.now().date()
        date_to = _parse_date(request.query_params.get("date_to"), today)
        date_from = _parse_date(request.query_params.get("date_from"), today)
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        # ---- Joriy holat (sana filtriga bog'liq emas) ----
        subs_qs = Subscription.objects.all()
        subscription_states = {
            "auto_renew_on": subs_qs.filter(status=Subscription.Status.ACTIVE, auto_renew=True).count(),
            "auto_renew_off_active": subs_qs.filter(status=Subscription.Status.ACTIVE, auto_renew=False).count(),
            "cancelled": subs_qs.filter(status=Subscription.Status.CANCELLED).count(),
            "pending": subs_qs.filter(status=Subscription.Status.PENDING).count(),
            "expired": subs_qs.filter(status=Subscription.Status.EXPIRED).count(),
        }

        cycles_qs = SubscriptionRenewalCycle.objects.all()
        cycle_states = {
            choice_value: cycles_qs.filter(status=choice_value).count()
            for choice_value, _ in SubscriptionRenewalCycle.Status.choices
        }

        # ---- Sana oralig'idagi urinishlar statistikasi ----
        attempts_qs = RenewalAttempt.objects.filter(attempted_at__date__gte=date_from, attempted_at__date__lte=date_to)
        range_stats = {
            "attempts_total": attempts_qs.count(),
            "attempts_success": attempts_qs.filter(result="success").count(),
            "attempts_failed": attempts_qs.exclude(result="success").count(),
            "unique_users_attempted": attempts_qs.values("cycle__subscription__user_id").distinct().count(),
        }

        # ---- Bugungi ko'rsatkichlar (sana filtridan mustaqil, doim "bugun") ----
        today_attempts_qs = RenewalAttempt.objects.filter(attempted_at__date=today)
        today_stats = {
            "attempts_today": today_attempts_qs.count(),
            "success_today": today_attempts_qs.filter(result="success").count(),
            "failed_today": today_attempts_qs.exclude(result="success").count(),
        }

        return Response({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "subscription_states": subscription_states,
            "cycle_states": cycle_states,
            "range_stats": range_stats,
            "today_stats": today_stats,
        })


class AdminRenewalSettingsView(APIView):
    """
    GET /api/admin/v1/renewal-settings/  — hamma is_staff xodim ko'ra oladi.
    PATCH /api/admin/v1/renewal-settings/ — faqat superuser o'zgartira oladi
    (to'lov vaqtlariga bevosita ta'sir qiladigan sozlama bo'lgani uchun).

    Singleton — har doim bitta qator (`RenewalSettings.load()`), id ko'rsatish shart emas.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsSuperUserForWrite]

    def get(self, request):
        from subscriptions.models import RenewalSettings
        from . import serializers as s

        obj = RenewalSettings.load()
        return Response(s.RenewalSettingsSerializer(obj).data)

    def patch(self, request):
        from subscriptions.models import RenewalSettings
        from . import serializers as s

        obj = RenewalSettings.load()
        serializer = s.RenewalSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class AdminAdmissionSettingsView(APIView):
    """
    GET /api/admin/v1/admission-settings/  — hamma is_staff xodim ko'ra oladi.
    PATCH /api/admin/v1/admission-settings/ — hamma is_staff xodim o'zgartira oladi
    (qabulni ochish/yopish operatsion qaror, superuser cheklovi shart emas).

    Singleton — `AdmissionSettings.load()`.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]

    def get(self, request):
        from growth.models import AdmissionSettings
        from . import serializers as s

        obj = AdmissionSettings.load()
        return Response(s.AdmissionSettingsSerializer(obj).data)

    def patch(self, request):
        from growth.models import AdmissionSettings
        from . import serializers as s

        obj = AdmissionSettings.load()
        serializer = s.AdmissionSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class AdminChannelSettingsView(APIView):
    """
    GET/PATCH /api/admin/v1/channel-settings/ — yopiq kanaldan avtomatik chiqarib
    yuborish uchun texnik sozlama (raqamli chat_id). Singleton — `ChannelSettings.load()`.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsSuperUserForWrite]

    def get(self, request):
        from cms.models import ChannelSettings
        from . import serializers as s

        obj = ChannelSettings.load()
        return Response(s.ChannelSettingsSerializer(obj).data)

    def patch(self, request):
        from cms.models import ChannelSettings
        from . import serializers as s

        obj = ChannelSettings.load()
        serializer = s.ChannelSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
