web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn tyrent_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 2
worker: celery -A tyrent_backend worker --loglevel=info --concurrency=2
beat: celery -A tyrent_backend beat --loglevel=info