from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminStaff


def _serialize_admin_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
        "last_login": user.last_login,
    }


class AdminLoginView(APIView):
    """
    POST /api/admin/v1/auth/login/
    Body: {"username": "...", "password": "..."}

    Django admin bilan bir xil hisob (``createsuperuser`` yoki Django adminda
    ``is_staff=True`` qilingan xodim) ishlatiladi — alohida ro'yxatdan o'tish shart emas.
    Muvaffaqiyatli bo'lsa doimiy token qaytaradi, admin panel uni har so'rovda
    ``Authorization: Token <key>`` header sifatida yuboradi.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response({"detail": "username va password majburiy"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Login yoki parol noto'g'ri"}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_staff:
            return Response({"detail": "Bu hisobda admin panelga kirish huquqi yo'q"}, status=status.HTTP_403_FORBIDDEN)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": _serialize_admin_user(user)})


class AdminLogoutView(APIView):
    """POST /api/admin/v1/auth/logout/ — joriy tokenni bekor qiladi (keyingi kirishda yangisi yaratiladi)."""

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminMeView(APIView):
    """GET /api/admin/v1/auth/me/ — joriy tizimga kirgan admin ma'lumotlari."""

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]

    def get(self, request):
        return Response(_serialize_admin_user(request.user))
