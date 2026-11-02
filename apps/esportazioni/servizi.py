"""Generazione dei file di esportazione: Excel, PDF, CSV."""
import csv
import io

from django.utils import timezone

from apps.fatti import statistiche

AVVERTENZA = (
    "I dati contano i fatti di reato riportati dai quotidiani online monitorati, non i reati commessi. "
    "La categoria è una stima giornalistica, non una qualificazione giuridica. "
    "Un arresto o una denuncia non sono una condanna."
)

COLONNE = ["ID", "Data", "Sintesi", "Reati", "Fase", "Ultimo sviluppo", "Regione", "Comune", "Quartiere", "Contesto",
           "Aggressione", "Arma", "Confidenza", "Stato revisione", "N. testate", "N. articoli", "Fonti"]


def riga(fatto) -> list:
    return [
        fatto.pk,
        fatto.data_evento,
        fatto.sintesi,
        ", ".join(c.nome for c in fatto.categorie.all()),
        fatto.get_fase_display(),
        fatto.data_ultimo_sviluppo,
        fatto.regione.nome if fatto.regione else "",
        fatto.comune.nome if fatto.comune else "",
        fatto.quartiere.nome if fatto.quartiere else "",
        fatto.get_contesto_display(),
        "sì" if fatto.aggressione else "no",
        fatto.get_arma_display(),
        fatto.get_confidenza_display(),
        fatto.get_stato_revisione_display(),
        fatto.n_testate,
        fatto.n_articoli,
        " ".join(a.url for a in fatto.articoli.all()),
    ]


def nome_file(estensione: str) -> str:
    return f"italia-criminale-{timezone.localdate():%Y-%m-%d}.{estensione}"


# ---------------- CSV ----------------
def genera_csv(qs) -> bytes:
    buffer = io.StringIO()
    w = csv.writer(buffer, delimiter=";")
    w.writerow(COLONNE)
    for fatto in qs.prefetch_related("articoli"):
        w.writerow(riga(fatto))
    return ("﻿" + buffer.getvalue()).encode("utf-8")  # BOM: Excel riconosce gli accenti


# ---------------- Excel ----------------
def genera_excel(qs, filtri_descr: str = "") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    intest = Font(bold=True, color="FFFFFF")
    sfondo = PatternFill("solid", fgColor="3A3A3A")

    def foglio(ws, titoli, righe, larghezze=None):
        ws.append(titoli)
        for cella in ws[1]:
            cella.font, cella.fill = intest, sfondo
        for r in righe:
            ws.append(list(r))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, larghezza in enumerate(larghezze or [], start=1):
            ws.column_dimensions[get_column_letter(i)].width = larghezza

    ws = wb.active
    ws.title = "Fatti"
    foglio(ws, COLONNE, (riga(f) for f in qs.prefetch_related("articoli")),
           [7, 11, 60, 30, 20, 14, 16, 18, 18, 18, 11, 14, 14, 18, 10, 10, 60])
    for cella in ws["C"][1:]:
        cella.alignment = Alignment(wrap_text=True, vertical="top")

    foglio(wb.create_sheet("Per reato"), ["Reato", "Macro-categoria", "Fatti"],
           ((r["categorie__nome"], r["categorie__macro__nome"], r["totale"]) for r in statistiche.per_categoria(qs)),
           [40, 32, 10])
    foglio(wb.create_sheet("Per regione"), ["Regione", "Fatti"],
           ((r["comune__provincia__regione__nome"], r["totale"]) for r in statistiche.per_regione(qs)), [28, 10])
    foglio(wb.create_sheet("Per città"), ["Comune", "Provincia", "Fatti", "Residenti", "Fatti ogni 100.000 residenti"],
           ((r["comune__nome"], r["comune__provincia__sigla"], r["totale"], r["comune__popolazione"],
             statistiche.tasso_per_100mila(r["totale"], r["comune__popolazione"]))
            for r in statistiche.per_comune(qs, limite=None)), [28, 10, 10, 12, 26])
    foglio(wb.create_sheet("Per quartiere"), ["Quartiere", "Comune", "Fatti"],
           ((r["quartiere__nome"], r["quartiere__comune__nome"], r["totale"])
            for r in statistiche.per_quartiere(qs, limite=None)), [30, 24, 10])
    foglio(wb.create_sheet("Per giorno"), ["Data", "Fatti"],
           ((r["giorno"], r["totale"]) for r in statistiche.per_giorno(qs)), [14, 10])

    e = statistiche.esiti(qs)
    foglio(wb.create_sheet("Esiti giudiziari"), ["Indicatore", "Valore"], [
        ("Fatti con un procedimento noto", e["procedimenti"]),
        ("Con esito noto (condanna, assoluzione, archiviazione)", e["con_esito"]),
        ("Quota con esito noto (%)", e["quota_con_esito"]),
        ("Condanne", e["condanne"]), ("Assoluzioni", e["assoluzioni"]), ("Archiviazioni", e["archiviazioni"]),
        (f"In attesa di esito da oltre {e['mesi_attesa']} mesi", e["in_attesa_da_oltre"]),
    ], [55, 12])
    foglio(wb.create_sheet("Copertura"), ["Fatti riportati da", "Fatti"],
           ((r["fascia"], r["totale"]) for r in statistiche.distribuzione_copertura(qs)), [22, 10])
    c = statistiche.cittadinanza(qs)
    ws_c = wb.create_sheet("Cittadinanza (aggregata)")
    foglio(ws_c, ["Cittadinanza autori come riportata", "Fatti", "% su tutti", "% sui fatti con cittadinanza indicata"],
           ((r["etichetta"], r["totale"], r["quota_su_tutti"], r["quota_su_indicati"]) for r in c["righe"]), [36, 10, 12, 34])
    ws_c.append([])
    ws_c.append(["La cittadinanza è indicata dai giornali in modo selettivo: le quote non stimano chi commette i reati."])
    foglio(wb.create_sheet("Cittadinanza per reato"),
           ["Reato", "Fatti", "Con cittadinanza indicata", "% indicata", "% straniera tra gli indicati"],
           ((r["categorie__nome"], r["totale"], r["indicati"], r["quota_indicata"], r["quota_straniera"])
            for r in statistiche.cittadinanza_per_categoria(qs, limite=None)), [40, 10, 24, 12, 26])
    foglio(wb.create_sheet("Cittadinanza per regione"),
           ["Regione", "Fatti", "Con cittadinanza indicata", "% straniera tra gli indicati", "% stranieri tra i residenti"],
           ((r["regione"], r["totale"], r["indicati"], r["quota_straniera_fatti"], r["quota_straniera_residenti"])
            for r in statistiche.cittadinanza_per_regione(qs)), [26, 10, 24, 26, 26])

    note = wb.create_sheet("Note")
    for testo in [
        "Italia Criminale – osservatorio sulla cronaca dei reati",
        f"Esportato il {timezone.localtime():%d/%m/%Y %H:%M}",
        f"Filtri: {filtri_descr or 'nessuno'}",
        "",
        AVVERTENZA,
    ]:
        note.append([testo])
    note.column_dimensions["A"].width = 120

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ---------------- PDF ----------------
def _grafico_categorie(qs) -> io.BytesIO | None:
    dati = [r for r in statistiche.per_categoria(qs, limite=10) if r["categorie__nome"]]
    if not dati:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker  # noqa: F401

    nomi = [r["categorie__nome"] for r in dati][::-1]
    valori = [r["totale"] for r in dati][::-1]
    fig, ax = plt.subplots(figsize=(7, 0.35 * len(dati) + 0.8), dpi=150)
    ax.barh(nomi, valori, color="#B3261E")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.set_xlabel("Fatti riportati", fontsize=8)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    img = io.BytesIO()
    fig.savefig(img, format="png")
    plt.close(fig)
    img.seek(0)
    return img


def genera_pdf(qs, filtri_descr: str = "", max_righe: int = 300) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title="Italia Criminale – report")
    stili = getSampleStyleSheet()
    piccolo = ParagraphStyle("piccolo", parent=stili["BodyText"], fontSize=7.5, leading=9)
    nota = ParagraphStyle("nota", parent=stili["BodyText"], fontSize=8, textColor=colors.HexColor("#555555"))

    r = statistiche.riepilogo(qs)
    storia = [
        Paragraph("Italia Criminale – report sulla cronaca dei reati", stili["Title"]),
        Paragraph(f"Generato il {timezone.localtime():%d/%m/%Y alle %H:%M} · Filtri: {filtri_descr or 'nessuno'}", nota),
        Spacer(1, 0.4 * cm),
        Table(
            [["Fatti", "Aggressioni", "Arresti", "Manifestazioni con esito", "Comuni"],
             [r["fatti"], r["aggressioni"], r["arresti"], r["manifestazioni"], r["comuni"]]],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
                ("TOPPADDING", (0, 1), (-1, 1), 8),
            ]),
            colWidths=[5 * cm] * 5,
        ),
        Spacer(1, 0.5 * cm),
    ]
    grafico = _grafico_categorie(qs)
    if grafico:
        storia += [Paragraph("Fatti per reato (prime 10 categorie)", stili["Heading2"]),
                   Image(grafico, width=16 * cm, height=16 * cm * 0.5, kind="proportional"), Spacer(1, 0.4 * cm)]

    storia.append(Paragraph("Elenco dei fatti", stili["Heading2"]))
    tabella = [["Data", "Sintesi", "Reati", "Fase", "Comune", "Quartiere", "Testate"]]
    for f in qs.prefetch_related("articoli")[:max_righe]:
        tabella.append([
            f.data_evento.strftime("%d/%m/%Y") if f.data_evento else "",
            Paragraph(f.sintesi, piccolo),
            Paragraph(", ".join(c.nome for c in f.categorie.all()), piccolo),
            Paragraph(f.get_fase_display(), piccolo),
            f.comune.nome if f.comune else "",
            f.quartiere.nome if f.quartiere else "",
            str(f.n_testate),
        ])
    t = Table(tabella, repeatRows=1, colWidths=[2 * cm, 9.5 * cm, 5 * cm, 3 * cm, 3 * cm, 3 * cm, 1.2 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3A3A3A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F3F3")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    storia.append(t)
    if qs.count() > max_righe:
        storia.append(Paragraph(f"Mostrati i primi {max_righe} fatti su {qs.count()}: per l'elenco completo usare l'esportazione Excel.", nota))
    storia += [Spacer(1, 0.5 * cm), Paragraph(AVVERTENZA, nota)]

    def piede(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(doc_.pagesize[0] - 1.5 * cm, 1 * cm, f"Pagina {doc_.page}")
        canvas.restoreState()

    doc.build(storia, onFirstPage=piede, onLaterPages=piede)
    return out.getvalue()
