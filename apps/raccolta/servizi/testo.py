"""Scaricamento ed estrazione del testo principale di un articolo."""
import hashlib

import trafilatura

from .http import client, consentito


class TestoNonDisponibile(Exception):
    pass


def scarica(url: str) -> dict:
    """Restituisce {'titolo', 'testo', 'data', 'hash'}."""
    if not consentito(url):
        raise TestoNonDisponibile("robots.txt non consente la lettura")
    with client() as c:
        r = c.get(url)
    if r.status_code != 200:
        raise TestoNonDisponibile(f"HTTP {r.status_code}")
    dati = trafilatura.bare_extraction(r.text, url=url, with_metadata=True, include_comments=False)
    if not dati or not getattr(dati, "text", None):
        raise TestoNonDisponibile("testo non estraibile")
    testo = dati.text.strip()
    return {
        "titolo": (dati.title or "").strip(),
        "testo": testo,
        "data": dati.date,
        "hash": hashlib.sha256(testo.encode()).hexdigest(),
    }
