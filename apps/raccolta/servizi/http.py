"""Client HTTP comune, con User-Agent dichiarato e rispetto di robots.txt."""
from functools import lru_cache
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from django.conf import settings


def client() -> httpx.Client:
    cfg = settings.RACCOLTA
    return httpx.Client(
        headers={"User-Agent": cfg["USER_AGENT"]},
        timeout=cfg["TIMEOUT_SECONDI"],
        follow_redirects=True,
    )


@lru_cache(maxsize=512)
def _robots(host_base: str) -> RobotFileParser:
    parser = RobotFileParser()
    try:
        with client() as c:
            r = c.get(f"{host_base}/robots.txt")
        parser.parse(r.text.splitlines() if r.status_code == 200 else [])
    except httpx.HTTPError:
        parser.parse([])
    return parser


def consentito(url: str) -> bool:
    parti = urlsplit(url)
    return _robots(f"{parti.scheme}://{parti.netloc}").can_fetch(settings.RACCOLTA["USER_AGENT"], url)
