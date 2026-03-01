"""
middleware/single_device.py
───────────────────────────────────────────────────────────────────────────────
SingleDeviceLoginMiddleware
───────────────────────────────────────────────────────────────────────────────
Enforces a "one active session per user" policy by binding each login to a
device-specific UUID stored both in the database (user.device_uuid) and in a
long-lived signed cookie on the client.

Flow
────
LOGIN  (handled by accounts/signals.py + this middleware's process_response)
  1. User authenticates → `user_logged_in` signal fires.
  2. Signal generates a new UUID, saves it to user.device_uuid, and stores
     the value in request._new_device_uuid.
  3. process_response() detects _new_device_uuid and sets the signed cookie.

EVERY SUBSEQUENT REQUEST  (process_request)
  1. Skip:  unauthenticated users — nothing to check.
  2. Bypass: staff/superuser accounts — admins are never locked out.
  3. Read the signed cookie (DEVICE_COOKIE_NAME from settings).
  4. If the cookie is missing → force logout, redirect to LOGIN_URL.
  5. If cookie UUID ≠ user.device_uuid → force logout, redirect to LOGIN_URL.
  6. Otherwise: let the request through normally.

Admin exception
───────────────
Any user with is_staff=True is fully exempt from the device check.
Superusers can also reset any user's lock via the "Reset device lock"
admin action (sets device_uuid=None; next login re-issues the UUID).
"""

import logging

from django.conf import settings
from django.contrib.auth import logout
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

    # ── process_request ────────────────────────────────────────────────────

    def __call__(self, request: HttpRequest):
        forced_logout = self._check_device(request)
        if forced_logout:
            return forced_logout  # Early redirect

        response = self.get_response(request)

        # After the view runs: if this was a fresh login, set the cookie.
        self._maybe_set_cookie(request, response)

        return response

    def _check_device(self, request: HttpRequest):
        """
        Validate the device cookie against the DB.
        Returns a redirect response on failure, None on success.
        """
        user = request.user

        # 1. Not logged in — nothing to check.
        if not user.is_authenticated:
            return None

        # 2. Staff / superusers bypass the lock entirely.
        if user.is_staff:
            return None

        # 3. Read the signed cookie.
        signed_token = request.COOKIES.get(self.cookie_name)

        if not signed_token:
            logger.warning(
                "Device cookie missing for user '%s' — forcing logout.", user.username
            )
            return self._force_logout(request)

        # 4. Verify the signature / expiry.
        token_value = _unsign(signed_token)
        if token_value is None:
            logger.warning(
                "Device cookie signature invalid for user '%s' — forcing logout.",
                user.username,
            )
            return self._force_logout(request)

        # 5. Compare with the DB value.
        db_uuid = str(user.device_uuid) if user.device_uuid else None
        if token_value != db_uuid:
            logger.info(
                "Device UUID mismatch for user '%s' (cookie=%s, db=%s) "
                "— session invalidated.",
                user.username,
                token_value,
                db_uuid,
            )
            return self._force_logout(request)

        # 6. All good.
        return None

    # ── Cookie management ──────────────────────────────────────────────────

    def _maybe_set_cookie(self, request: HttpRequest, response):
        """
        If a fresh UUID was generated during this request cycle (login),
        attach the signed cookie to the response.
        """
        new_uuid = getattr(request, "_new_device_uuid", None)
        if new_uuid is None:
            return

        signed = _sign(new_uuid)
        response.set_cookie(
            self.cookie_name,
            signed,
            max_age=self.cookie_age,
            httponly=True,
            samesite="Lax",
            # secure=True  ← set automatically by Django when SECURE_SSL_REDIRECT
            secure=not settings.DEBUG,
        )
        logger.info(
            "Device cookie issued for user '%s'.",
            request.user.username if request.user.is_authenticated else "unknown",
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _force_logout(self, request: HttpRequest):
        """Log the user out and redirect to the login page."""
        logout(request)
        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        response = redirect(login_url)
        # Also delete the stale cookie from the client.
        response.delete_cookie(self.cookie_name)
        return response
