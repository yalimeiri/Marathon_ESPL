web: python manage.py migrate --no-input && python manage.py collectstatic --no-input && gunicorn marathonlms.wsgi --timeout 300 --workers 2 --log-file -
