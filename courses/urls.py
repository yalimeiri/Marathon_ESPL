"""
courses/urls.py
"""

from django.urls import path
from . import views

app_name = "courses"

urlpatterns = [
    # Category list → /courses/
    path("", views.CategoryListView.as_view(), name="category-list"),

    # Video list for a specific category → /courses/category/<pk>/
    path("category/<int:pk>/", views.VideoListView.as_view(), name="video-list"),

    # Individual video detail → /courses/video/<pk>/
    path("video/<int:pk>/", views.VideoDetailView.as_view(), name="video-detail"),

    # Payment page → /courses/category/<pk>/payment/
    path("category/<int:pk>/payment/", views.PaymentView.as_view(), name="payment"),

    # Telegram Webhook endpoint (Bot Token acts as security path variable)
    path("webhook/telegram/<str:bot_token>/", views.telegram_webhook, name="telegram-webhook"),

    # ── Upload Manager (superuser only) ────────────────────────────────────
    path("manager/upload/", views.upload_video_page, name="upload-video"),
    path("manager/save-video/", views.save_video, name="save-video"),
]
