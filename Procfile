release: python manage.py migrate --noinput && python manage.py carica_dati_base
web: gunicorn config.wsgi --log-file -
