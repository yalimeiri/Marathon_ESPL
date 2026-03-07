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
     the value in request._new_device_uuid (first-time) or
     request._existing_device_uuid (returning user).
  3. process_response() detects _new_device_uuid and sets the signed cookie.
  4. For returning users (_existing_device_uuid), we compare their *incoming*
     cookie against the DB. If they differ, ths is a second device → block.

EVERY SUBSEQUENT REQUEST  (process_request)
  1. Skip:  unauthenticated users — nothing to check.
  2. Bypass: staff/superuser accounts — admins are never locked out.
  3. Bypass: login and logout URLs (prevent redirect loops).
  4. Read the signed cookie (DEVICE_COOKIE_NAME from settings).
  5. If the cookie is missing → force logout, redirect to LOGIN_URL.
  6. If cookie UUID ≠ user.device_uuid → force logout, redirect to LOGIN_URL.
  7. Otherwise: let the request through normally.

Admin exception
───────────────
Any user with is_staff=True is fully exempt from the device check.
Superusers can also reset any user's lock via the "Reset device lock"
admin action (sets device_uuid=None; next login re-issues the UUID).
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
        # --- PRE-VIEW: Block illegitimate current sessions ---
        forced_logout = self._check_device(request)
        if forced_logout:
            return forced_logout

        # --- Run the actual view ---
        response = self.get_response(request)

        # --- POST-VIEW: Handle fresh logins ---
        # Case A: Brand new user/device — issued a fresh UUID this request cycle.
        #         Set the cookie on the response so the browser stores it.
        new_uuid = getattr(request, "_new_device_uuid", None)
        if new_uuid and request.user.is_authenticated:
            # Suffix cookie with user pk so multiple users sharing a PC don't overwrite each other
            user_cookie_name = f"{self.cookie_name}_{request.user.pk}"
            self._set_cookie(response, user_cookie_name, new_uuid)
            logger.info("Device cookie issued for user '%s'.", 
                        getattr(request.user, "username", "?"))

        # Case B: Returning user logging in — they already have a UUID in DB.
        #         We already have their incoming cookie. If it matches the DB we let
        #         them through. If not, we block them RIGHT NOW (after the login view
        #         ran but before the browser follows the redirect).
        existing_uuid = getattr(request, "_existing_device_uuid", None)
        if existing_uuid and request.user.is_authenticated and not request.user.is_staff:
            user_cookie_name = f"{self.cookie_name}_{request.user.pk}"
            incoming_signed = request.COOKIES.get(user_cookie_name)
            incoming_uuid = _unsign(incoming_signed) if incoming_signed else None

            if incoming_uuid != existing_uuid:
                logger.warning(
                    "POST-LOGIN BLOCK: user '%s' from unknown device "
                    "(cookie=%s, db=%s).",
                    request.user.username, incoming_uuid, existing_uuid,
                )
                return self._force_logout(request)

        return response

    # ── Device Validation ──────────────────────────────────────────────────

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
        if (path.startswith(login_url) or 
            path.startswith(logout_url) or 
            path.startswith(register_url)):
            return None

        # Read and validate the signed cookie.
        user_cookie_name = f"{self.cookie_name}_{user.pk}"
        signed_token = request.COOKIES.get(user_cookie_name)

        if not signed_token:
            logger.warning("Device cookie missing for '%s' — logging out.", user.username)
            return self._force_logout(request)

        token_value = _unsign(signed_token)
        if token_value is None:
            logger.warning("Bad device cookie signature for '%s' — logging out.", user.username)
            return self._force_logout(request)

        db_uuid = str(user.device_uuid) if user.device_uuid else None
        if token_value != db_uuid:
            logger.info(
                "Device mismatch for '%s' (cookie=%s, db=%s) — logging out.",
                user.username, token_value, db_uuid,
            )
            return self._force_logout(request)

        # All good.
        return None

    # ── Cookie management ──────────────────────────────────────────────────

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

    # ── Helpers ────────────────────────────────────────────────────────────

    def _force_logout(self, request: HttpRequest):
        """Log the user out and redirect to login with a visible error."""
        logout(request)

        # Add error message AFTER logout so it survives into the new anonymous session.
        messages.error(
            request,
            "Your account is linked to another device. "
            "You cannot access it from this browser."
        )

        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        login_url += "?blocked=1"
        return redirect(login_url)
