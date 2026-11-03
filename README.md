# Italia Criminale

Osservatorio sulla **cronaca** dei reati in Italia: raccoglie gli articoli dei quotidiani online,
li raggruppa in fatti, li classifica per reato e luogo e pubblica statistiche con le fonti sempre linkate.
I numeri contano i fatti riportati dai giornali, non i reati commessi.

## Avvio rapido

```bash
cd ~/Scrivania/"ITALIA CRIMINALE"
./setup.sh                      # crea/ripara l'ambiente virtuale, migra il DB, carica regioni e tassonomia
source .venv/bin/activate
python manage.py createsuperuser
python manage.py runserver      # http://127.0.0.1:8000  ·  amministrazione: /admin
```

## Flusso di lavoro quotidiano

1. In **/admin → Testate** aggiungi le testate con i loro feed RSS e i comuni coperti.
2. Importa i comuni ISTAT (una volta): `python manage.py importa_comuni elenco-comuni.csv`
3. Raccogli e analizza:
   ```bash
   python manage.py raccogli_feed       # nuovi articoli dai feed
   python manage.py elabora_articoli    # testo > estrazione > luogo > fatto (+ ricontrolli degli aggiornamenti)
   python manage.py pulisci_testi       # cancella i testi integrali oltre il periodo di conservazione
   ```
   In produzione si pianificano con cron (es. ogni 30 minuti).

   Seguiti giudiziari: gli articoli su processi, sentenze e assoluzioni vengono collegati al fatto originale
   anche a distanza di anni (fino a 12). Per l'elenco dei procedimenti senza esito:
   `python manage.py fatti_senza_esito --mesi 12 --csv da_seguire.csv`
4. In **/admin → Fatti** filtra per "Da rivedere" e verifica le classificazioni (i seguiti giudiziari vanno sempre controllati).
5. In **/admin → Regioni/Comuni** inserisci residenti e residenti stranieri ISTAT per i confronti sulla cittadinanza.
6. In **/admin → Testate** imposta l'orientamento (uso interno, con la fonte della classificazione):
   il confronto è nella pagina riservata allo staff `/interno/orientamento/`.

Dopo un aggiornamento del codice: `python manage.py migrate` (e, se servono, `python manage.py ricalcola_contatori`).

### Scelte sui dati sensibili

- **Cittadinanza**: solo se scritta nella fonte, mai dedotta. Sul sito e nell'API compare solo in forma aggregata,
  con la quota "non indicata" sempre in evidenza; non si può filtrare l'elenco dei singoli fatti per cittadinanza.
- **Orientamento politico delle testate**: solo in amministrazione e nella pagina interna, mai pubblicato.

Con `ANTHROPIC_API_KEY` nel file `.env` l'estrazione usa un LLM; senza, un classificatore a parole chiave (solo per sviluppo).

## Struttura

| Cartella | Contenuto |
| --- | --- |
| `config/` | impostazioni, URL principali |
| `apps/territorio` | regioni, province, comuni, quartieri; import ISTAT |
| `apps/reati` | tassonomia dei reati e valori degli attributi (fase, contesto, arma…) |
| `apps/fonti` | testate, articoli, versioni degli articoli |
| `apps/fatti` | fatti, fonti del fatto, cronologia, revisioni, segnalazioni; filtri e statistiche |
| `apps/raccolta` | feed RSS, estrazione testo, LLM, deduplicazione, geocoding, comandi |
| `apps/esportazioni` | Excel, PDF, CSV (rispettano i filtri attivi) |
| `apps/pagine` | sito pubblico: home, fatti, scheda, statistiche, mappa, metodologia |
| `apps/api` | API REST in sola lettura (`/api/fatti/`, `/api/statistiche/`…) |
| `tests/` | test con pytest |

## Comandi utili

```bash
pytest                 # test
ruff check .           # controllo stile
```

## Produzione

- `DATABASE_URL=postgres://…` nel `.env` (PostgreSQL consigliato), `DEBUG=False`, `ALLOWED_HOSTS`.
- `python manage.py collectstatic` e avvio con `gunicorn config.wsgi`.
- Geocoding: per volumi reali usare un'istanza Nominatim propria (`NOMINATIM_URL`).
- Prima del lancio pubblico: parere legale su GDPR (art. 10), diritto d'autore e text and data mining.

## Pubblicazione su Heroku

```bash
heroku git:remote -a italia-criminale
heroku addons:create heroku-postgresql:essential-0
heroku config:set SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')" \
  DEBUG=False ALLOWED_HOSTS=.herokuapp.com \
  CSRF_TRUSTED_ORIGINS=https://italia-criminale-XXXX.herokuapp.com
git push heroku main
heroku run python manage.py importa_comuni
heroku run python manage.py carica_testate
heroku run python manage.py raccogli_giorno
heroku run python manage.py createsuperuser
```

- `Procfile`: a ogni rilascio applica le migrazioni e carica regioni e tassonomia.
- Raccolta automatica: add-on **Heroku Scheduler**, con `python manage.py raccogli_giorno` ogni notte
  ed `python manage.py elabora_articoli` ogni ora.
