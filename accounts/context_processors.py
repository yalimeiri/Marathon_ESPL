from django.conf import settings


def registration_settings(request):
    return {
        "ALLOW_EMAIL_REGISTRATION": getattr(settings, "ALLOW_EMAIL_REGISTRATION", True),
    }
