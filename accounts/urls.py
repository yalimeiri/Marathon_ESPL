from django.urls import path
from .views import RegisterView, CustomPasswordResetConfirmView
from .debug_views import email_test

app_name = "accounts"

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('email-test/', email_test, name='email-test'),  # TEMPORARY — remove after fixing email
    # Override Django's default password reset confirm to clear device_uuid on reset
    path(
        'reset/<uidb64>/<token>/',
        CustomPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
]

