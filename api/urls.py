from django.urls import path
from . import views, payment_form_views

urlpatterns = [
    # pay.turdievakademiyasi.uz forma backendi (ochiq, Telegram authsiz — tokenning o'zi himoya)
    path("payment/form/<uuid:token>/", payment_form_views.PaymentFormDetailView.as_view(), name="payment-form-detail"),
    path("payment/form/<uuid:token>/process", payment_form_views.PaymentFormProcessView.as_view(), name="payment-form-process"),
    path("payment/form/<uuid:token>/verify", payment_form_views.PaymentFormVerifyView.as_view(), name="payment-form-verify"),

    path("card-replacement/form/<uuid:token>/", payment_form_views.CardReplacementFormDetailView.as_view(), name="card-replacement-form-detail"),
    path("card-replacement/form/<uuid:token>/process", payment_form_views.CardReplacementFormProcessView.as_view(), name="card-replacement-form-process"),
    path("card-replacement/form/<uuid:token>/verify", payment_form_views.CardReplacementFormVerifyView.as_view(), name="card-replacement-form-verify"),

    path("subscription/status/", views.SubscriptionStatusView.as_view(), name="subscription-status"),
    path("gifts/track/", views.GiftTrackView.as_view(), name="gift-track"),
    path("gifts/<int:month_number>/claim/", views.GiftClaimView.as_view(), name="gift-claim"),

    path("materials/", views.MaterialListView.as_view(), name="material-list"),

    path("content/categories/", views.ContentCategoryListView.as_view(), name="content-category-list"),
    path("content/categories/<int:category_id>/subcategories/", views.ContentSubcategoryListView.as_view(), name="content-subcategory-list"),
    path("content/categories/<int:category_id>/items/", views.ContentListView.as_view(), name="content-list"),
    path("content/<int:content_id>/", views.ContentDetailView.as_view(), name="content-detail"),
    path("content/<int:content_id>/like/", views.ContentLikeToggleView.as_view(), name="content-like-toggle"),
    path("content/liked/", views.LikedContentListView.as_view(), name="content-liked-list"),

    path("community/categories/", views.CommunityCategoryListView.as_view(), name="community-category-list"),
    path("community/categories/<int:category_id>/items/", views.CommunityContentListView.as_view(), name="community-content-list"),
]