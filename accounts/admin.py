"""
accounts/admin.py
─────────────────────────────────────────────────────────────────────────────
Registers CustomUser in the Django Admin with:
  • All the built-in UserAdmin fields.
  • A read-only display of device_uuid.
  • A custom admin action "Reset device lock" that clears device_uuid,
    forcing the next login to re-issue a fresh UUID (and kick any active
    session that doesn't re-login).
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser


@admin.action(description="🔓 Reset device lock (clear device UUID)")
def reset_device_lock(modeladmin, request, queryset):
    """Clear device_uuid for selected users, effectively unlocking them."""
    updated = queryset.update(device_uuid=None)
    modeladmin.message_user(
        request,
        f"Device lock reset for {updated} user(s). "
        "Their next login will re-issue a new device UUID.",
    )


@admin.action(description="🗑️ Delete selected users")
def delete_selected_users(modeladmin, request, queryset):
    """Deletes the selected users permanently."""
    count = queryset.count()
    queryset.delete()
    modeladmin.message_user(
        request,
        f"{count} user(s) deleted successfully.",
    )


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    actions = [reset_device_lock, delete_selected_users]
    # Show delete link on the individual user detail page
    show_full_result_count = True

    # Add device_uuid to the detail view (read-only — managed by the system)
    readonly_fields = UserAdmin.readonly_fields + ("device_uuid",)

    fieldsets = UserAdmin.fieldsets + (
        (
            _("Device Security"),
            {
                "fields": ("device_uuid",),
                "description": (
                    "The UUID of the last device that logged in. "
                    "Use the 'Reset device lock' action to clear this "
                    "and allow the user to log in from a new device."
                ),
            },
        ),
    )

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "device_uuid",
    )
    list_filter = UserAdmin.list_filter
    search_fields = ("username", "email", "first_name", "last_name")
