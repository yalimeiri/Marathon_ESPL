"""
accounts/signals.py
───────────────────────────────────────────────────────────────────────────────
Handles the device-lock lifecycle on login and password reset.

When a user authenticates:
  1. If they have NO device_uuid (fresh account or admin-reset):
     → A fresh UUID is generated, saved to DB, and stored on the request so
       the middleware can set the signed cookie on the response.
  2. If they already HAVE a device_uuid (returning user):
     → The existing UUID is stored on the request so the middleware can check
       whether the browser presenting the login request holds the matching cookie.

When a user successfully resets their password:
  → device_uuid is cleared, allowing the NEXT login (from any device) to
    re-issue a new lock.  This is safe because the device-restricted
    CustomPasswordResetView already ensures only the original device can
    trigger the reset email.
"""

import uuid
import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth import get_user_model

logger = logging.getLogger("middleware.single_device")

User = get_user_model()


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Generate a new device UUID only if the user doesn't have one
    (first-device-wins policy).
    """
    if user.is_staff:
        # Staff accounts are never device-locked.
        return

    if not user.device_uuid:
        new_uuid = uuid.uuid4()
        user.device_uuid = new_uuid
        user.save(update_fields=["device_uuid"])

        # Stash on request so SingleDeviceLoginMiddleware can set the cookie.
        request._new_device_uuid = str(new_uuid)
        request._device_lock_user_pk = user.pk
        logger.info("Device UUID issued for user '%s': %s", user.username, new_uuid)
    else:
        logger.info("User '%s' is already bound to a device.", user.username)
        # We must STILL attach the existing UUID to the request.
        # Why? Because if they are logging in from a new device, the middleware
        # needs to see they have an existing lock and check if their browser cookie matches it.
        request._existing_device_uuid = str(user.device_uuid)
        request._device_lock_user_pk = user.pk


def _clear_device_uuid_for_user(user):
    """Clear the device lock so the next login re-issues a new UUID."""
    if user.device_uuid:
        user.device_uuid = None
        user.save(update_fields=["device_uuid"])
        logger.info(
            "Device UUID cleared for user '%s' after password reset. "
            "Next login will re-issue a new device lock.",
            user.username,
        )
