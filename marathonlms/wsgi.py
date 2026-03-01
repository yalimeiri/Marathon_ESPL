"""
WSGI config for MarathonLMS.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "marathonlms.settings")
application = get_wsgi_application()
