"""
MarathonLMS — Root URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django Admin (obscured URL to reduce automated attacks)
    path("marathon-manage-X7k2/", admin.site.urls),

    # Accounts (login / logout / password reset — Django built-ins + custom register)
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("accounts.urls", namespace="accounts")),

    # Courses (single include — avoids W005 duplicate namespace)
    path("courses/", include("courses.urls", namespace="courses")),

    # Root → redirect to course list
    path("", RedirectView.as_view(pattern_name="courses:category-list", permanent=False)),
]

# ── Serve media files in development only ───────────────────────────────────
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
