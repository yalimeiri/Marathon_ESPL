import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    email = models.EmailField(_("email address"), blank=True, unique=True)
    """
    Extends Django's built-in AbstractUser with a device_uuid field used
    by the SingleDeviceLoginMiddleware to enforce single-device login.

    device_uuid is nullable — a NULL value means "no active device lock"
    (e.g. after an admin reset, the next login will re-issue a new UUID).
    """

    device_uuid = models.UUIDField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Device UUID",
        help_text=(
            "UUID of the last device that logged in. "
            "Set to NULL via the admin to unlock the account."
        ),
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.username
