"""
courses/urls.py
"""

from django.urls import path
from . import views

app_name = "courses"

urlpatterns = [
    # Category list → /courses/
    path("", views.CategoryListView.as_view(), name="category-list"),

    # FAQ list → /courses/faq/
    path("faq/", views.FAQListView.as_view(), name="faq-list"),

    # Video list for a specific category → /courses/category/<pk>/
    path("category/<int:pk>/", views.VideoListView.as_view(), name="video-list"),

    # Past exam Q&A → /courses/category/<pk>/qa/
    path("category/<int:pk>/qa/", views.ExamQuestionListView.as_view(), name="exam-qa"),

    # Reference materials → /courses/category/<pk>/resources/
    path("category/<int:pk>/resources/", views.ResourceListView.as_view(), name="resources"),

    # Individual video detail → /courses/video/<pk>/
    path("video/<int:pk>/", views.VideoDetailView.as_view(), name="video-detail"),

    # Payment page → /courses/category/<pk>/payment/
    path("category/<int:pk>/payment/", views.PaymentView.as_view(), name="payment"),

    # Telegram Webhook endpoint (authenticated via X-Telegram-Bot-Api-Secret-Token header)
    path("webhook/telegram/", views.telegram_webhook, name="telegram-webhook"),

    # ── Upload Manager (superuser only) ────────────────────────────────────
    path("manager/upload/", views.upload_video_page, name="upload-video"),
    path("manager/save-video/", views.save_video, name="save-video"),

    # ── Video Q&A ──────────────────────────────────────────────────────────
    path("video/<int:video_pk>/ask/", views.ask_question, name="ask-question"),
    path("question/<int:question_pk>/answer/", views.post_answer, name="post-answer"),
]
