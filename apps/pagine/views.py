import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, redirect, render

from apps.fatti import statistiche
from apps.fatti.filtri import filtra
from apps.fatti.models import Caso, Fatto
from apps.fonti.models import Testata

from .avvisi import avvisa_segnalazione, invia_contatto
from .forms import ContattoForm, SegnalazioneForm


def _querystring(request):
    q = request.GET.copy()
    q.pop("pagina", None)
    return q.urlencode()


def _filtri_attivi(filtro) -> str:
    """Riassunto leggibile dei filtri in uso, mostrato in cima quando il modulo è in fondo alla pagina."""
    from apps.esportazioni.views import _descrivi_filtri

    return _descrivi_filtri(filtro)


def _casi_con_numeri():
    from django.db.models import Count, F, Max

    return (Caso.objects.annotate(ultimo=Max("articoli__pubblicato_il"), n=Count("articoli", distinct=True))
            .filter(n__gt=0).order_by(F("ultimo").desc(nulls_last=True), "ordine"))


def home(request):
    qs = Fatto.objects.pubblicati().con_relazioni()
    return render(request, "pagine/home.html", {
        "casi": _casi_con_numeri().filter(in_evidenza=True)[:6],
        "riepilogo": statistiche.riepilogo(qs),
        "ultimi": qs.recenti()[:10],
        "categorie": statistiche.per_categoria(qs, limite=8),
        "testate": Testata.objects.filter(attiva=True).count(),
    })


def elenco_fatti(request):
    filtro = filtra(request.GET)
    risultati = filtro.qs if request.GET.get("ordina") else filtro.qs.recenti()
    pagina = Paginator(risultati, 30).get_page(request.GET.get("pagina"))
    return render(request, "pagine/fatti.html", {
        "filtro": filtro, "pagina": pagina, "qs": _querystring(request), "filtri_attivi": _filtri_attivi(filtro),
    })


def dettaglio_fatto(request, pk):
    fatto = get_object_or_404(Fatto.objects.pubblicati().con_relazioni(), pk=pk)
    form = SegnalazioneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        segnalazione = form.save(commit=False)
        segnalazione.fatto = fatto
        segnalazione.save()
        avvisa_segnalazione(request, segnalazione)
        messages.success(request, "Grazie, la segnalazione è stata registrata.")
        return redirect("dettaglio_fatto", pk=pk)
    fonti = fatto.fattoarticolo_set.select_related("articolo__testata").order_by("articolo__testata__nome", "articolo__pubblicato_il")
    per_testata = {}
    for fa in fonti:
        per_testata.setdefault(fa.articolo.testata, []).append(fa)
    return render(request, "pagine/fatto.html", {
        "fatto": fatto, "per_testata": per_testata, "form": form,
        "eventi": fatto.eventi.select_related("articolo__testata"),
    })


def statistiche_view(request):
    filtro = filtra(request.GET, statistiche=True)
    qs = filtro.qs
    comuni = statistiche.per_comune(qs)
    for c in comuni:
        c["tasso"] = statistiche.tasso_per_100mila(c["totale"], c["comune__popolazione"])
    dati_grafici = {
        "giorni": [{"x": r["giorno"], "y": r["totale"]} for r in statistiche.per_giorno(qs)],
        "categorie": [{"x": r["categorie__nome"], "y": r["totale"]} for r in statistiche.per_categoria(qs, limite=12) if r["categorie__nome"]],
    }
    return render(request, "pagine/statistiche.html", {
        "filtro": filtro,
        "qs": _querystring(request),
        "filtri_attivi": _filtri_attivi(filtro),
        "riepilogo": statistiche.riepilogo(qs),
        "regioni": statistiche.per_regione(qs),
        "comuni": comuni,
        "quartieri": statistiche.per_quartiere(qs),
        "esiti": statistiche.esiti(qs),
        "piu_ripresi": statistiche.piu_ripresi(qs),
        "copertura": statistiche.distribuzione_copertura(qs),
        "cittadinanza": statistiche.cittadinanza(qs),
        "cittadinanza_categorie": statistiche.cittadinanza_per_categoria(qs),
        "cittadinanza_regioni": statistiche.cittadinanza_per_regione(qs),
        "dati_grafici": json.dumps(dati_grafici, cls=DjangoJSONEncoder),
    })


def mappa(request):
    filtro = filtra(request.GET)
    punti = [
        {"id": f.pk, "lat": f.lat, "lon": f.lon, "sintesi": f.sintesi,
         "data": f.data_evento.strftime("%d/%m/%Y") if f.data_evento else ""}
        for f in filtro.qs.exclude(lat=None)[:2000] if f.mostra_coordinate
    ]
    return render(request, "pagine/mappa.html", {
        "filtro": filtro, "punti": json.dumps(punti), "filtri_attivi": _filtri_attivi(filtro),
    })


def metodologia(request):
    return render(request, "pagine/metodologia.html", {"testate": Testata.objects.filter(attiva=True)})


@staff_member_required
def interno_orientamento(request):
    """Pagina riservata allo staff: la copertura cambia con la linea editoriale della testata?"""
    from apps.fonti.models import Articolo, Testata

    return render(request, "pagine/interno_orientamento.html", {
        "righe": statistiche.copertura_per_orientamento(Articolo.objects.all()),
        "non_classificate": Testata.objects.filter(attiva=True, orientamento="non_classificata").count(),
    })


def fatti_del_giorno(request, giorno=None):
    """Tutti i fatti di un giorno, raggruppati per regione e città."""
    from datetime import date, timedelta

    from django.http import Http404
    from django.shortcuts import redirect as _redirect
    from django.utils import timezone

    if giorno is None and request.GET.get("d"):
        return _redirect("fatti_del_giorno_data", giorno=request.GET["d"])
    oggi = timezone.localdate()
    if giorno is None:
        giorno = oggi - timedelta(days=1)
    else:
        try:
            giorno = date.fromisoformat(giorno)
        except ValueError as e:
            raise Http404("Data non valida") from e
    base = Fatto.objects.pubblicati().con_relazioni()
    qs = base.filter(data_evento=giorno).order_by(
        "provincia__regione__nome", "provincia__nome", "comune__nome", "-n_testate"
    )
    # notizie del giorno su fatti precedenti o senza data (processi, sentenze, anniversari)
    sviluppi = base.filter(data_ultimo_sviluppo=giorno).exclude(data_evento=giorno).order_by("-n_testate")
    gruppi = {}
    for f in qs:
        regione = f.regione.nome if f.regione else "Luogo non individuato"
        gruppi.setdefault(regione, []).append(f)
    if "Luogo non individuato" in gruppi:
        gruppi["Luogo non individuato"] = gruppi.pop("Luogo non individuato")
    return render(request, "pagine/giorno.html", {
        "giorno": giorno,
        "precedente": giorno - timedelta(days=1),
        "successivo": giorno + timedelta(days=1) if giorno < oggi else None,
        "gruppi": gruppi,
        "sviluppi": sviluppi,
        "riepilogo": statistiche.riepilogo(qs),
        "categorie": statistiche.per_categoria(qs, limite=8),
        "qs": f"dal={giorno.isoformat()}&al={giorno.isoformat()}",
    })


def casi(request):
    return render(request, "pagine/casi.html", {"casi": _casi_con_numeri()})


def caso(request, slug):
    from django.db.models import Count, Max, Min

    caso = get_object_or_404(Caso, slug=slug)
    articoli = caso.articoli.select_related("testata").prefetch_related("fatti").order_by("-pubblicato_il", "-rilevato_il")
    numeri = articoli.aggregate(primo=Min("pubblicato_il"), ultimo=Max("pubblicato_il"),
                                testate=Count("testata", distinct=True))
    reati = caso.reati().con_relazioni().recenti()
    return render(request, "pagine/caso.html", {
        "caso": caso,
        "numeri": numeri,
        "pagina": Paginator(articoli, 50).get_page(request.GET.get("pagina")),
        "n_articoli": articoli.count(),
        "reati": reati[:30],
        "n_reati": reati.count(),
        "ultima_fase": reati.exclude(fase="notizia").first(),
        "per_provincia": (reati.exclude(provincia=None).values("provincia__nome", "provincia__sigla")
                          .annotate(n=Count("id", distinct=True)).order_by("-n")[:10]) if caso.tipo == Caso.Tipo.TEMA else [],
        "mostra_riassunto": caso.riassunto_verificato or request.user.is_staff,
    })


def pagina_statica(request, modello):
    from django.conf import settings

    return render(request, f"pagine/{modello}.html", {"titolare": settings.TITOLARE_NOME})


def contatti(request):
    form = ContattoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data.get("sito_web"):  # compilato solo dai programmi di spam
            invia_contatto(form.cleaned_data | {"motivo": dict(ContattoForm.MOTIVI)[form.cleaned_data["motivo"]]})
        messages.success(request, "Grazie, il messaggio è stato inviato. Ti risponderemo all'email indicata.")
        return redirect("contatti")
    return render(request, "pagine/contatti.html", {"form": form})
