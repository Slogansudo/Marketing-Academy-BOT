from django.urls import path
from .webhooks import PaymeWebhookView, TributeWebhookView

urlpatterns = [
    path("payme/webhook/", PaymeWebhookView.as_view(), name="payme-webhook"),
    path("tribute/webhook/", TributeWebhookView.as_view(), name="tribute-webhook"),
]
