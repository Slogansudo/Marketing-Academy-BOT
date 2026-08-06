# from django.contrib import admin
# from django.urls import path, include, re_path
# from django.views.static import serve
# from django.conf import settings
# from django.conf.urls.static import static
#
# urlpatterns = [
#     path("admin/", admin.site.urls),
#     path("api/v1/", include("api.urls")),
#     path("api/admin/v1/", include("admin_api.urls")),   # Admin panel API (full CRUD)
#     path("bot/", include("bot.urls")),                 # Telegram webhook
#     path("payments/", include("subscriptions.webhook_urls")),  # Payme/Tribute webhooklari
# ]
#
# # if settings.DEBUG:
# #     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#
#
# if settings.DEBUG:
#     urlpatterns += [
#         re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
#         re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
#     ]
# else:
#     urlpatterns += [
#         re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
#         re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
#     ]





















from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, Http404


def spa_view(document_root):
    """SPA fallback: real fayl bo'lsa uni beradi, aks holda index.html (client-side routing)."""
    def view(request, path=""):
        full_path = document_root / path
        if path and full_path.is_file():
            return serve(request, path, document_root=document_root)
        index = document_root / "index.html"
        if not index.is_file():
            raise Http404
        return FileResponse(open(index, "rb"))
    return view


ACADEMY_ADMIN_DIST = settings.BASE_DIR / "frontend_dist" / "academy_admin"
MINIAPP_DIST = settings.BASE_DIR / "frontend_dist" / "miniapp"


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.urls")),
    path("api/admin/v1/", include("admin_api.urls")),   # Admin panel API (full CRUD)
    path("bot/", include("bot.urls")),                 # Telegram webhook
    path("payments/", include("subscriptions.webhook_urls")),  # Payme/Tribute webhooklari

    # --- Frontend'lar (static SPA) ---
    re_path(r"^academy/admin/(?P<path>.*)$", spa_view(ACADEMY_ADMIN_DIST)),
    re_path(r"^miniapp/(?P<path>.*)$", spa_view(MINIAPP_DIST)),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
