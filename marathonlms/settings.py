"""
MarathonLMS — settings.py
───────────────────────────────────────────────────────────────────────────────
Reads secrets & configuration from environment variables (or a .env file)
via python-decouple so no credentials ever live in source control.

Local Dev  → SQLite, DEBUG=True, local media storage
Production → PostgreSQL (DATABASE_URL), DEBUG=False,
             WhiteNoise for static, optionally S3 for media.
"""

import os
from pathlib import Path

from decouple import Csv, config, UndefinedValueError
import hmac

# ── Base directory ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-before-production")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

# Auto-add Railway domain if running on Railway
_RAILWAY_DOMAIN = os.environ.get("RAILWAY_STATIC_URL", "")
if _RAILWAY_DOMAIN and _RAILWAY_DOMAIN not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_RAILWAY_DOMAIN)

# Also add the public Railway URL
_RAILWAY_PUBLIC = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
if _RAILWAY_PUBLIC and _RAILWAY_PUBLIC not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_RAILWAY_PUBLIC)

# CSRF trusted origins (required for admin forms in production)
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("*", "127.0.0.1", "localhost")
]
# Ensure Railway domains are trusted for POST requests
if _RAILWAY_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_RAILWAY_DOMAIN}")
if _RAILWAY_PUBLIC:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_RAILWAY_PUBLIC}")

CSRF_TRUSTED_ORIGINS += config(
    "CSRF_TRUSTED_ORIGINS", default="", cast=Csv()
)

# ── HTTPS & Security ────────────────────────────────────────────────────────
# In production on Railway, HTTPS is handled by their proxy. We need to tell
# Django to trust the strict HTTPS header from the proxy.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ── Application definition ──────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django built-ins
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",  # serves static in dev too (optional)
    "django.contrib.staticfiles",
    # Third-party
    "anymail",
    "storages",
    "axes",
    # Django Sites (required by allauth)
    "django.contrib.sites",
    # Google OAuth / Social Login
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Project apps
    "accounts.apps.AccountsConfig",
    "courses.apps.CoursesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # ← must be just after SecurityMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "middleware.single_device.SingleDeviceLoginMiddleware",  # ← device-lock
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",  # ← brute-force login protection
    "allauth.account.middleware.AccountMiddleware",  # ← required by allauth
]

ROOT_URLCONF = "marathonlms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.registration_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "marathonlms.wsgi.application"

# ── Unfold Admin Settings ───────────────────────────────────────────────────
from django.templatetags.static import static

UNFOLD = {
    "SITE_TITLE": "Marathon ESPL Admin",
    "SITE_HEADER": "Marathon ESPL",
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("courses/img/marathon-logo.svg"),  # fallback
        "dark": lambda request: static("courses/img/marathon-logo.svg"),
    },
    "COLORS": {
        "primary": {
            "50": "250 253 255",
            "100": "240 249 255",
            "200": "224 242 254",
            "300": "186 230 253",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
        },
    },
    "SHOW_HISTORY": True, 
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "courses.admin_dashboard.dashboard_callback",
    "STYLES": [
        lambda request: static("courses/css/admin_overrides.css"),
    ],
}

# ── Database ────────────────────────────────────────────────────────────────
import dj_database_url

_DATABASE_URL = config("DATABASE_URL", default="")

if _DATABASE_URL:
    # Production: parse any standard PostgreSQL URL format
    # (Railway, Heroku, Render all use slightly different prefixes —
    #  dj-database-url handles them all)
    DATABASES = {
        "default": dj_database_url.parse(
            _DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Local development: SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ── Authentication ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/courses/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ── Django Sites (required by allauth) ──────────────────────────────────────
SITE_ID = 1

# ── Allauth / Google OAuth ───────────────────────────────────────────────────
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True  # Link Google to existing email/password accounts
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# ── Registration mode ────────────────────────────────────────────────────────
# True  → dev: email/password register + password reset available
# False → prod: Google sign-in only, register/reset pages return 404
ALLOW_EMAIL_REGISTRATION = config("ALLOW_EMAIL_REGISTRATION", default=True, cast=bool)

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": config("GOOGLE_CLIENT_ID", default=""),
            "secret": config("GOOGLE_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# ── Email ────────────────────────────────────────────────────────────────────
# Uses SMTP in production (configure via environment variables on Railway).
# Falls back to console backend in development (emails print to terminal).
import logging

_email_logger = logging.getLogger("marathonlms.email")

_EMAIL_HOST = config("EMAIL_HOST", default="")
_BREVO_API_KEY = config("BREVO_API_KEY", default="")

if _BREVO_API_KEY:
    # ── Brevo HTTP API (works on Railway — SMTP is blocked) ──────────────────
    EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
    ANYMAIL = {
        "BREVO_API_KEY": _BREVO_API_KEY,
    }
    DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
    if not DEFAULT_FROM_EMAIL:
        if not DEBUG:
            from django.core.exceptions import ImproperlyConfigured

            raise ImproperlyConfigured(
                "DEFAULT_FROM_EMAIL must be set when using BREVO_API_KEY. "
                "Use a sender address verified in your Brevo dashboard."
            )
        _email_logger.warning(
            "BREVO_API_KEY is set but DEFAULT_FROM_EMAIL is empty — emails will fail."
        )
elif _EMAIL_HOST:
    # ── Fallback: SMTP (may be blocked by Railway) ───────────────────────────
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _EMAIL_HOST
    EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
    _raw_password = config("EMAIL_HOST_PASSWORD", default="")
    EMAIL_HOST_PASSWORD = _raw_password.replace(" ", "")
    EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
    EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
    EMAIL_USE_SSL = False
    EMAIL_TIMEOUT = 10
    DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)
else:
    # ── Local dev: print to console ──────────────────────────────────────────
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "noreply@marathonlms.com"




# ── Internationalisation ────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static files (WhiteNoise serves via middleware — no special storage needed) ─
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ── Media files ─────────────────────────────────────────────────────────────
#
#  LOCAL development (default)
#  ─────────────────────────────
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

#
#  ── S3 / DigitalOcean Spaces (uncomment to activate) ───────────────────────
#  Set USE_S3=True in .env and fill the S3_* variables.
#
# USE_S3 = config("USE_S3", default=False, cast=bool)
# if USE_S3:
#     AWS_ACCESS_KEY_ID       = config("AWS_ACCESS_KEY_ID")
#     AWS_SECRET_ACCESS_KEY   = config("AWS_SECRET_ACCESS_KEY")
#     AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
#     AWS_S3_REGION_NAME      = config("AWS_S3_REGION_NAME", default="us-east-1")
#     AWS_S3_CUSTOM_DOMAIN    = config("AWS_S3_CUSTOM_DOMAIN", default=None)
#     AWS_DEFAULT_ACL         = "private"
#     AWS_S3_FILE_OVERWRITE   = False
#     AWS_QUERYSTRING_AUTH    = True   # pre-signed URLs for private videos
#
#     STORAGES = {
#         "default": {
#             "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
#         },
#         "staticfiles": {
#             "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
#         },
#     }
#
#
# ── Bunny.net Stream ────────────────────────────────────────────────────────
# IMPORTANT: Set these in Railway env vars. Never commit real keys here.
BUNNY_LIBRARY_ID = config("BUNNY_LIBRARY_ID", default="")
BUNNY_API_KEY = config("BUNNY_API_KEY", default="")
BUNNY_PULL_ZONE = config("BUNNY_PULL_ZONE", default="")

# ── Telegram Webhook Settings ───────────────────────────────────────────────
# IMPORTANT: Set these in Railway env vars. Never commit real tokens here.
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = config("TELEGRAM_CHAT_ID", default="")
TELEGRAM_WEBHOOK_SECRET = config("TELEGRAM_WEBHOOK_SECRET", default="")


# ── Device Lock ─────────────────────────────────────────────────────────────
DEVICE_COOKIE_NAME = "device_token"
# Signed cookies expire after 30 days (seconds)
DEVICE_COOKIE_AGE = 60 * 60 * 24 * 30

# ── Default primary-key type ─────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
        "middleware.single_device": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "marathonlms.email": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ── Production-hardening (only apply when not in DEBUG) ──────────────────────
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000          # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Railway (and most PaaS) terminate SSL at the load balancer.
    # Django must NOT redirect to HTTPS itself — use the proxy header instead.
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Django-Axes: Brute-force login protection ────────────────────────────────
AXES_FAILURE_LIMIT = 5              # Lock after 5 failed attempts
AXES_COOLOFF_TIME = 1               # 1 hour lockout
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]  # Track by both username and IP
AXES_RESET_ON_SUCCESS = True        # Reset failed count after a successful login
AXES_LOCKOUT_TEMPLATE = "accounts/lockout.html"  # Friendly page instead of bare 403
# Railway runs behind a proxy — tell axes to read the real IP from X-Forwarded-For
AXES_IPWARE_PROXY_COUNT = 1
