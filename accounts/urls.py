from django.urls import path
from .views import RegisterView
from .debug_views import email_test

app_name = "accounts"

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('email-test/', email_test, name='email-test'),  # TEMPORARY — remove after fixing email
]

