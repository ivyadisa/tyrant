web: python manage.py collectstatic --noinput --clear && python manage.py migrate && gunicorn tyrent_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 180
worker: celery -A tyrent_backend worker --loglevel=info --concurrency=2
beat: celery -A tyrent_backend beat --loglevel=info