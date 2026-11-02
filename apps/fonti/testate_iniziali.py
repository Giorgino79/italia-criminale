"""Primo elenco di testate nazionali con feed RSS di cronaca.

Gli indirizzi dei feed cambiano spesso: il comando raccogli_giorno indica quali non rispondono,
e si correggono da /admin → Testate. L'orientamento resta "non classificata": va impostato
in amministrazione indicando la fonte della classificazione.
"""
TESTATE = [
    ("ANSA", "https://www.ansa.it", ["https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml"]),
    ("la Repubblica", "https://www.repubblica.it", ["https://www.repubblica.it/rss/cronaca/rss2.0.xml"]),
    ("Corriere della Sera", "https://www.corriere.it", ["https://xml2.corriereobjects.it/rss/cronache.xml"]),
    ("La Stampa", "https://www.lastampa.it", ["https://www.lastampa.it/rss/cronaca"]),
    ("Il Fatto Quotidiano", "https://www.ilfattoquotidiano.it", ["https://www.ilfattoquotidiano.it/cronaca/feed/"]),
    ("Sky TG24", "https://tg24.sky.it", ["https://tg24.sky.it/rss/tg24_cronaca.xml"]),
    ("TGCom24", "https://www.tgcom24.mediaset.it", ["https://www.tgcom24.mediaset.it/rss/cronaca.xml"]),
    ("RaiNews", "https://www.rainews.it", ["https://www.rainews.it/rss/cronaca"]),
    ("Il Messaggero", "https://www.ilmessaggero.it", ["https://www.ilmessaggero.it/rss/italia.xml"]),
    ("Fanpage", "https://www.fanpage.it", ["https://www.fanpage.it/feed/"]),
    ("Today", "https://www.today.it", ["https://www.today.it/rss"]),
]
