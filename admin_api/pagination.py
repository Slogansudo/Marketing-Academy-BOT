from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class AdminPagination(PageNumberPagination):
    """
    Admin panel jadvallari uchun: sahifa hajmini frontend o'zi tanlashi mumkin
    (``?page_size=50``), javobda umumiy son va sahifalar soni ham qaytadi —
    admin jadval komponentlari uchun qulay.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "total_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "page_size": self.get_page_size(self.request),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })
