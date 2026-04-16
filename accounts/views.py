from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth import login, get_user_model
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .forms import CustomUserCreationForm

User = get_user_model()


class RegisterView(CreateView):
    """
    Handles user registration.
    On successful form submission, the user is saved, auto-logged in,
    and sent a welcome email.
    """
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('courses:category-list')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')

        try:
            site_url = self.request.build_absolute_uri('/courses/')
            send_mail(
                subject="ברוך הבא ל-TheFlyingSquirrel!",
                message=(
                    f"שלום {user.username},\n\n"
                    f"ההרשמה שלך הסתיימה בהצלחה!\n\n"
                    f"שם משתמש: {user.username}\n\n"
                    f"כדי להיכנס לאתר: {site_url}\n\n"
                    f"שים לב: החשבון שלך נעול למחשב/דפדפן שבו נרשמת.\n\n"
                    f"בברכה,\nצוות TheFlyingSquirrel"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass

        return super().form_valid(form)


class CustomPasswordResetView(PasswordResetView):
    """
    Override PasswordResetView to block reset requests from unauthorized devices.

    SECURITY POLICY:
      - If the email belongs to a user who has a registered device (device_uuid set),
        we check whether the browser making the request holds the matching device cookie.
      - If the cookie is MISSING or WRONG → the request is rejected with an error.
      - Only the original registered device/browser can request a password reset.
    """

    def form_valid(self, form):
        from middleware.single_device import _unsign

        email = form.cleaned_data.get("email", "").strip().lower()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Let Django handle non-existent emails (silently ignores them)
            return super().form_valid(form)

        # If the user has no device_uuid yet, they haven't logged in from any
        # device, so no restriction applies.
        if not user.device_uuid:
            return super().form_valid(form)

        # Staff/superusers can reset from any device
        if user.is_staff:
            return super().form_valid(form)

        # Check the device cookie in the current browser
        base_cookie_name = getattr(settings, "DEVICE_COOKIE_NAME", "device_token")
        cookie_name = f"{base_cookie_name}_{user.pk}"
        signed_token = self.request.COOKIES.get(cookie_name)
        token_value = _unsign(signed_token) if signed_token else None
        db_uuid = str(user.device_uuid)

        if token_value != db_uuid:
            # Wrong device — block the reset and show a clear error
            messages.error(
                self.request,
                "🔒 איפוס סיסמה אפשרי רק מהמכשיר המקורי שבו נרשמת. "
                "השתמש במחשב/דפדפן המקורי שלך כדי לאפס את הסיסמה."
            )
            from django.shortcuts import redirect
            from django.urls import reverse
            return redirect(reverse("accounts:password_reset"))

        return super().form_valid(form)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    After a successful password reset, clear the device UUID so that the
    NEXT login (from any device) re-issues a fresh device lock.
    This is safe because CustomPasswordResetView already ensures only the
    original device can trigger the reset email.
    """

    def form_valid(self, form):
        # Let Django save the new password first
        response = super().form_valid(form)

        # Now clear the device lock so the user can re-bind their device
        user = self.user  # PasswordResetConfirmView sets self.user
        if user and not user.is_staff:
            from accounts.signals import _clear_device_uuid_for_user
            _clear_device_uuid_for_user(user)

        return response
