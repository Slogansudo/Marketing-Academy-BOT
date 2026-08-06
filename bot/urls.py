from django.urls import path
from . import views

urlpatterns = [
    path("webhook/<str:secret>/", views.telegram_webhook, name="telegram-webhook"),
]
