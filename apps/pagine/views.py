import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, redirect, render

from apps.fatti import statistiche
from apps.fatti.filtri import filtra
from apps.fatti.models import Fatto
from apps.fonti.models import Testata

from .avvisi import avvisa_segnalazione
from .forms import SegnalazioneForm


def _querystring(request):
    q = request.GET.copy()
    q.pop("pagina", None)
    return q.urlencode()


def home(request):
    qs = Fatto.objects.pubblicati().con_relazioni()
    return render(request, "pagine/home.html", {
        "riepilogo": statistiche.riepilogo(qs),
        "ultimi": qs[:10],
        "categorie": statistiche.per_categoria(qs, limite=8),
        "testate": Testata.objects.filter(attiva=True).count(),
    })


def elenco_fatti(request):
    filtro = filtra(request.GET)
    pagina = Paginator(filtro.qs, 30).get_page(request.GET.get("pagina"))
    return render(request, "pagine/fatti.html", {"filtro": filtro, "pagina": pagina, "qs": _querystring(request)})


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
    return render(request, "pagine/mappa.html", {"filtro": filtro, "punti": json.dumps(punti)})


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
    qs = Fatto.objects.pubblicati().con_relazioni().filter(data_evento=giorno).order_by(
        "provincia__regione__nome", "provincia__nome", "comune__nome", "-n_testate"
    )
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
        "riepilogo": statistiche.riepilogo(qs),
        "categorie": statistiche.per_categoria(qs, limite=8),
        "qs": f"dal={giorno.isoformat()}&al={giorno.isoformat()}",
    })
