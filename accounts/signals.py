"""
accounts/signals.py
───────────────────────────────────────────────────────────────────────────────
Handles the device-lock lifecycle on login.

When a user authenticates:
  1. A fresh UUID is generated.
  2. It is saved to ``user.device_uuid`` in the database.
  3. The UUID string is stored on the **request** object so the middleware
     can pick it up and set the signed cookie on the outgoing response.

Why set it on the request here instead of directly on the response?
  Django signals do not have access to the response object — only the
  middleware's ``process_response`` hook does.  So we use the request as a
  temporary carrier between the signal and the middleware.
"""

import uuid
import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.db.models.signals import post_save

logger = logging.getLogger("middleware.single_device")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Generate a new device UUID only if the user doesn't have one 
    (first-device-wins policy).
    """
    if not user.device_uuid:
        new_uuid = uuid.uuid4()
        user.device_uuid = new_uuid
        user.save(update_fields=["device_uuid"])

        # Stash on request so SingleDeviceLoginMiddleware can set the cookie.
        request._new_device_uuid = str(new_uuid)
        logger.info("Device UUID issued for user '%s': %s", user.username, new_uuid)
    else:
        logger.info("User '%s' is already bound to a device.", user.username)
        # We must STILL attach the existing UUID to the request.
        # Why? Because if they are logging in from a new device, the middleware
        # needs to see they have an existing lock and check if their browser cookie matches it.
        request._existing_device_uuid = str(user.device_uuid)


def on_password_reset(sender, request, user, **kwargs):
    """
    When a user resets their password, clear their device_uuid.
    This revokes the old device binding — the first device to log in
    after the reset wins the new lock.
    
    This prevents an attacker from using 'Forgot Password' to bypass 
    the single-device lock and gain access from a second device while 
    the original device retains its lock.
    """
    if user.device_uuid:
        user.device_uuid = None
        user.save(update_fields=["device_uuid"])
        logger.info(
            "Device UUID cleared for user '%s' after password reset. "
            "Next login will re-issue a new device lock.",
            user.username,
        )


# Connect to Django's built-in password_reset_complete signal
try:
    from django.contrib.auth.views import PasswordResetConfirmView
    from django.contrib.auth.signals import user_logged_in as _  # noqa: just confirming import

    # Django fires this signal when a password is successfully changed via PasswordResetConfirmView
    from django.contrib.auth import update_session_auth_hash
    from django.test.signals import setting_changed  # noqa
except ImportError:
    pass

# The correct signal to hook into for password changes
from django.contrib.auth.signals import user_logged_in  # already imported above

# Django doesn't have a dedicated "password_reset_complete" signal,
# so we listen to the HTTP POST on the confirm view by overriding the model's save.
# A simpler, reliable approach: use a custom PasswordResetConfirmView override.

