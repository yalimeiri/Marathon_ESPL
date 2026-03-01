"""
Accounts app configuration.

The ``ready()`` method connects the ``user_logged_in`` signal, which is
responsible for generating and persisting the device UUID on every login.
The signed cookie is then attached to the response inside the middleware.
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        # Import the signal handlers so they get connected on startup.
        import accounts.signals  # noqa: F401
