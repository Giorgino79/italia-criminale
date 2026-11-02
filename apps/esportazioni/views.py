from django.http import HttpResponse

from apps.fatti.filtri import filtra

from . import servizi


def _descrivi_filtri(filtro) -> str:
    if not filtro.is_bound or not filtro.form.is_valid():
        return ""
    parti = []
    for nome, valore in filtro.form.cleaned_data.items():
        if valore not in (None, "", []):
            parti.append(f"{filtro.form.fields[nome].label}: {valore}")
    return "; ".join(parti)


def _risposta(contenuto: bytes, tipo: str, estensione: str) -> HttpResponse:
    r = HttpResponse(contenuto, content_type=tipo)
    r["Content-Disposition"] = f'attachment; filename="{servizi.nome_file(estensione)}"'
    return r


def esporta_excel(request):
    f = filtra(request.GET)
    return _risposta(servizi.genera_excel(f.qs, _descrivi_filtri(f)),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx")


def esporta_pdf(request):
    f = filtra(request.GET)
    return _risposta(servizi.genera_pdf(f.qs, _descrivi_filtri(f)), "application/pdf", "pdf")


def esporta_csv(request):
    f = filtra(request.GET)
    return _risposta(servizi.genera_csv(f.qs), "text/csv; charset=utf-8", "csv")
