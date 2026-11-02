#!/usr/bin/env bash
# Crea (o ricrea) l'ambiente virtuale e prepara il database.
set -e
cd "$(dirname "$0")"
if ! .venv/bin/python -c "import django" 2>/dev/null; then
  echo "Creo l'ambiente virtuale..."
  rm -rf .venv
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements/dev.txt
fi
[ -f .env ] || cp .env.example .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py carica_dati_base
echo "Pronto. Avvia con: source .venv/bin/activate && python manage.py runserver"
