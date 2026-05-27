from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth import login, get_user_model
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import Http404
import logging

from .forms import CustomUserCreationForm
from courses.free_access import try_grant_free_access

User = get_user_model()
logger = logging.getLogger("marathonlms.email")


class RegisterView(CreateView):
    """
    Handles user registration.
    On successful form submission, the user is saved, auto-logged in,
    and sent a welcome email.
    """
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('courses:category-list')

    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "ALLOW_EMAIL_REGISTRATION", True):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')

        # ── Free Access Campaign ──────────────────────────────────────────
        slot_granted = try_grant_free_access(user)
        if slot_granted:
            messages.success(
                self.request,
                "🎉 מזל טוב! קיבלת גישה חינמית לכל הקורסים הכלולים במבצע!"
            )

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
    Also disabled entirely when ALLOW_EMAIL_REGISTRATION is False (Google-only prod).

    SECURITY POLICY:
      - If the email belongs to a user who has a registered device (device_uuid set),
        we check whether the browser making the request holds the matching device cookie.
      - If the cookie is MISSING or WRONG → the request is rejected with an error.
      - Only the original registered device/browser can request a password reset.
    """

    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "ALLOW_EMAIL_REGISTRATION", True):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def _device_allows_password_reset(self, user):
        """Return True if this user may request a reset from the current browser."""
        from middleware.single_device import _unsign

        if not user.device_uuid or user.is_staff:
            return True

        base_cookie_name = getattr(settings, "DEVICE_COOKIE_NAME", "device_token")
        cookie_name = f"{base_cookie_name}_{user.pk}"
        signed_token = self.request.COOKIES.get(cookie_name)
        token_value = _unsign(signed_token) if signed_token else None
        return token_value == str(user.device_uuid)

    def form_valid(self, form):
        from django.shortcuts import redirect
        from django.urls import reverse

        email = form.cleaned_data.get("email", "").strip().lower()
        users = User.objects.filter(email__iexact=email)

        if not users.exists():
            return super().form_valid(form)

        if users.count() == 1:
            user = users.first()
            if not self._device_allows_password_reset(user):
                messages.error(
                    self.request,
                    "🔒 איפוס סיסמה אפשרי רק מהמכשיר המקורי שבו נרשמת. "
                    "השתמש במחשב/דפדפן המקורי שלך כדי לאפס את הסיסמה."
                )
                return redirect(reverse("accounts:password_reset"))

        try:
            return super().form_valid(form)
        except Exception:
            logger.exception("Password reset email failed for %s", email)
            messages.error(
                self.request,
                "We could not send the reset email. Please try again later or contact support.",
            )
            return redirect(reverse("accounts:password_reset"))


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    After a successful password reset, clear the device UUID so that the
    NEXT login (from any device) re-issues a fresh device lock.
    This is safe because CustomPasswordResetView already ensures only the
    original device can trigger the reset email.
    """

    def form_valid(self, form):
        response = super().form_valid(form)

        user = self.user  # PasswordResetConfirmView sets self.user
        if user and not user.is_staff:
            from accounts.signals import _clear_device_uuid_for_user
            _clear_device_uuid_for_user(user)

        return response
