"""Download the lists and store them in the DB (shared by every process)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.utils import timezone

from . import conf
from .checks import reset_caches
from .models import Blocklist, normalize_domain

logger = logging.getLogger("disposable_email")


class UpdateError(Exception):
    """The download failed or looked wrong; the previous list was kept."""


@dataclass
class UpdateResult:
    count: int
    added: int
    removed: int


def parse(text: str) -> set[str]:
    domains = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line and "." in line and " " not in line:
            domains.add(normalize_domain(line))
    return domains


def download(url: str) -> set[str]:
    import requests

    response = requests.get(url, timeout=conf.get("TIMEOUT"),
                            headers={"User-Agent": "django-disposable-email"})
    response.raise_for_status()
    return parse(response.text)


def update_blocklist(sources: list[str] | None = None) -> UpdateResult:
    """Download every source; keep the old list if any source fails or looks too short."""
    sources = list(sources if sources is not None else conf.get("SOURCES"))
    domains: set[str] = set()
    for url in sources:
        try:
            found = download(url)
        except Exception as exc:  # noqa: BLE001
            raise UpdateError(f"{url}: {exc}") from exc
        if len(found) < conf.get("MIN_DOMAINS"):
            raise UpdateError(f"{url}: only {len(found)} domains (minimum {conf.get('MIN_DOMAINS')})")
        domains |= found
    previous = Blocklist.objects.filter(pk=1).values_list("domains", flat=True).first() or ""
    old = set(previous.split())
    Blocklist.objects.update_or_create(pk=1, defaults={
        "domains": "\n".join(sorted(domains)), "count": len(domains),
        "sources": sources, "fetched_at": timezone.now(),
    })
    reset_caches()
    result = UpdateResult(count=len(domains), added=len(domains - old), removed=len(old - domains))
    logger.info("disposable_email: list updated | count=%s added=%s removed=%s",
                result.count, result.added, result.removed)
    return result
