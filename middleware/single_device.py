"""
middleware/single_device.py
───────────────────────────────────────────────────────────────────────────────
SingleDeviceLoginMiddleware
───────────────────────────────────────────────────────────────────────────────
Enforces a "one active session per user" policy by binding each login to the
DEVICE THAT FIRST REGISTERED / LOGGED IN.  The binding is stored:
  • In the database:  user.device_uuid
  • In the browser:   a long-lived, signed HttpOnly cookie

Flow
────
LOGIN  (accounts/signals.py + this middleware's __call__ post-view section)
  1. User submits credentials → Django's login view authenticates them.
  2. The `user_logged_in` signal fires and sets one of:
       request._new_device_uuid      — first login ever (UUID freshly issued)
       request._existing_device_uuid — returning user already has a UUID in DB
     In both cases request._device_lock_user_pk is set to the user's pk.
  3. POST-VIEW (this middleware):
     a) New device UUID  → set the signed cookie on the response.
     b) Existing UUID    → check if the browser's cookie matches the DB UUID.
        Mismatch = second device → force logout immediately.

EVERY SUBSEQUENT REQUEST  (pre-view in __call__)
  1. Skip unauthenticated users.
  2. Bypass staff / superusers entirely.
  3. Bypass /login, /logout, /register, and allauth OAuth paths.
  4. Read the signed cookie.
  5. Cookie missing or bad signature → force logout.
  6. Cookie UUID ≠ user.device_uuid in DB → force logout.
  7. All good → let the request through.
"""

import logging

from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpRequest
from django.shortcuts import redirect

logger = logging.getLogger("middleware.single_device")

_SIGNER = TimestampSigner(salt="marathon_device_lock")


def _sign(value: str) -> str:
    return _SIGNER.sign(value)


def _unsign(signed_value: str) -> str | None:
    """Return the original value, or None if the signature is bad / expired."""
    try:
        max_age = getattr(settings, "DEVICE_COOKIE_AGE", 60 * 60 * 24 * 30)
        return _SIGNER.unsign(signed_value, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


class SingleDeviceLoginMiddleware:
    """
    Middleware that enforces single-device login for non-staff users.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.cookie_name = getattr(settings, "DEVICE_COOKIE_NAME", "device_token")
        self.cookie_age = getattr(settings, "DEVICE_COOKIE_AGE", 60 * 60 * 24 * 30)

    def __call__(self, request: HttpRequest):
        # ── PRE-VIEW: block illegitimate sessions ─────────────────────────
        forced_logout = self._check_device(request)
        if forced_logout:
            return forced_logout

        # ── Run the actual view ───────────────────────────────────────────
        response = self.get_response(request)

        # ── POST-VIEW: handle fresh logins ────────────────────────────────
        # We use _device_lock_user_pk (set by the signal) rather than
        # request.user.pk because request.user can be stale when
        # AuthenticationMiddleware cached it before the login view ran.
        user_pk = getattr(request, "_device_lock_user_pk", None)

        # Case A: Brand-new device UUID just issued.
        new_uuid = getattr(request, "_new_device_uuid", None)
        if new_uuid and user_pk:
            user_cookie_name = f"{self.cookie_name}_{user_pk}"
            self._set_cookie(response, user_cookie_name, new_uuid)
            logger.info(
                "Device cookie issued for user pk=%s uuid=%s.", user_pk, new_uuid
            )

        # Case B: Returning user with an existing device lock.
        # Check whether the browser presenting the login request already holds
        # the correct cookie.  If not → this is a second device → block it.
        existing_uuid = getattr(request, "_existing_device_uuid", None)
        if existing_uuid and user_pk:
            user_cookie_name = f"{self.cookie_name}_{user_pk}"
            incoming_signed = request.COOKIES.get(user_cookie_name)
            incoming_uuid = _unsign(incoming_signed) if incoming_signed else None

            if incoming_uuid != existing_uuid:
                logger.warning(
                    "POST-LOGIN BLOCK: user pk=%s tried from another device "
                    "(cookie_uuid=%s, db_uuid=%s).",
                    user_pk, incoming_uuid, existing_uuid,
                )
                return self._force_logout(request)

        return response

    # ── Device Validation ─────────────────────────────────────────────────

    def _check_device(self, request: HttpRequest):
        """
        Validate the device cookie on every authenticated, non-exempt request.
        Returns a redirect response on failure, None to continue normally.
        """
        user = request.user

        # Not logged in — nothing to check.
        if not user.is_authenticated:
            return None

        # Staff / superusers bypass the lock entirely.
        if user.is_staff:
            return None

        # Bypass auth-related URLs to prevent redirect loops.
        path = request.path_info
        login_url  = getattr(settings, "LOGIN_URL",  "/accounts/login/")
        logout_url = getattr(settings, "LOGOUT_URL", "/accounts/logout/")
        register_url = "/accounts/register/"
        # Bypass allauth OAuth flow paths (user is unauthenticated during these,
        # but the explicit bypass guards against edge cases with intermediate pages).
        if (
            path.startswith(login_url)
            or path.startswith(logout_url)
            or path.startswith(register_url)
            or path.startswith("/accounts/google/")
            or path.startswith("/accounts/social/")
        ):
            return None

        # Read and validate the signed cookie.
        user_cookie_name = f"{self.cookie_name}_{user.pk}"
        signed_token = request.COOKIES.get(user_cookie_name)

        if not signed_token:
            logger.warning(
                "Device cookie missing for user '%s' — logging out.", user.username
            )
            return self._force_logout(request)

        token_value = _unsign(signed_token)
        if token_value is None:
            logger.warning(
                "Bad device cookie signature for user '%s' — logging out.",
                user.username,
            )
            return self._force_logout(request)

        db_uuid = str(user.device_uuid) if user.device_uuid else None
        if token_value != db_uuid:
            logger.info(
                "Device mismatch for user '%s' (cookie=%s, db=%s) — logging out.",
                user.username, token_value, db_uuid,
            )
            return self._force_logout(request)

        # All good.
        return None

    # ── Cookie management ─────────────────────────────────────────────────

    def _set_cookie(self, response, cookie_name: str, uuid_value: str):
        signed = _sign(uuid_value)
        response.set_cookie(
            cookie_name,
            signed,
            max_age=self.cookie_age,
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG,
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _force_logout(self, request: HttpRequest):
        """Log the user out and redirect to login with a visible error."""
        logout(request)

        messages.error(
            request,
            "🔒 החשבון שלך נעול למכשיר אחר. לא ניתן להיכנס מדפדפן/מחשב אחר.",
        )

        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        return redirect(login_url + "?blocked=1")
