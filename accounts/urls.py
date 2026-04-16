from django.urls import path
from .views import RegisterView, CustomPasswordResetView, CustomPasswordResetConfirmView

app_name = "accounts"

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    # Override built-in password reset: check device cookie before sending email
    path(
        'password-reset/',
        CustomPasswordResetView.as_view(),
        name='password_reset',
    ),
    # Override built-in reset confirm (keeping device_uuid intact)
    path(
        'reset/<uidb64>/<token>/',
        CustomPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
]

