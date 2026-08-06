from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.filters import OrderingFilter, SearchFilter

from .pagination import AdminPagination
from .permissions import IsAdminStaff


class AdminModelViewSet(viewsets.ModelViewSet):
    """
    Admin panel API dagi barcha ViewSet'lar shu klassdan meros oladi:

    - Autentifikatsiya: Token (``Authorization: Token <key>``) yoki Django sessiya
      (Django admin bilan bir xil login qilingan bo'lsa) — mini app'ning
      ``TelegramInitDataAuthentication`` bilan mutlaqo aralashmaydi.
    - Ruxsat: faqat ``is_staff=True`` xodimlar.
    - Qidiruv/filtr/tartiblash/pagination — barcha endpointlarda bir xilda ishlaydi.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAdminStaff]
    pagination_class = AdminPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
