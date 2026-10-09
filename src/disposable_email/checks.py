"""Core check: is this email allowed?

Order: allowed by hand (``DomainRule`` allow) > blocked by hand (``DomainRule``
block) > disposable (bundled list + last download). Domains match with their
subdomains (``x.mailinator.com`` is ``mailinator.com``).

Everything is cached per process and refreshed lazily, so it is cheap to call
on every signup and every worker sees changes without restarting:

- the downloaded list, every ``REFRESH_SECONDS`` (stored in the DB by
  ``update_disposable_domains``);
- the admin rules, every ``RULES_REFRESH_SECONDS`` (and at once in the process
  that saves them);
- the on/off switch, every ``ENABLED_CACHE_SECONDS`` when it comes from the
  DB or a callable.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from django.db import DatabaseError
from django.utils.module_loading import import_string

from . import conf
from .models import normalize_domain

logger = logging.getLogger("disposable_email")

DISPOSABLE = "disposable"
BLOCKED = "blocked"
INVALID = "invalid"

_lock = threading.RLock()
_state: dict = {}


def reset_caches() -> None:
    """Forget every cached value in this process (tests, admin saves, updates)."""
    with _lock:
        _state.clear()


@dataclass(frozen=True)
class Verdict:
    blocked: bool
    reason: str = ""  # "" | "disposable" | "blocked" | "invalid"
    domain: str = ""

    def __bool__(self):  # truthy = blocked
        return self.blocked


# ── on/off ───────────────────────────────────────────────────────────────


def _resolve_enabled() -> bool:
    value = conf.get("ENABLED")
    if isinstance(value, bool):
        return value
    if value == "db":
        from .models import Config

        try:
            row = Config.objects.filter(pk=1).values_list("enabled", flat=True).first()
        except DatabaseError:
            return True  # table not migrated yet: fail closed (protected)
        return True if row is None else row
    if isinstance(value, str):
        try:
            return bool(import_string(value)())
        except Exception:  # noqa: BLE001 — a broken switch must not open the door
            logger.exception("disposable_email: ENABLED callable %r failed; blocking stays on", value)
            return True
    if callable(value):
        return bool(value())
    return bool(value)


def is_enabled() -> bool:
    """Is blocking switched on? (bool, "db" or callable; see conf.py)."""
    if isinstance(conf.get("ENABLED"), bool):
        return conf.get("ENABLED")
    now = time.monotonic()
    with _lock:
        cached = _state.get("enabled")
        if cached and now - cached[1] < conf.get("ENABLED_CACHE_SECONDS"):
            return cached[0]
    value = _resolve_enabled()
    with _lock:
        _state["enabled"] = (value, now)
    return value


# ── lists ────────────────────────────────────────────────────────────────


def package_domains() -> frozenset[str]:
    if not conf.get("INCLUDE_PACKAGE_LIST"):
        return frozenset()
    with _lock:
        if "package" not in _state:
            from disposable_email_domains import blocklist

            _state["package"] = frozenset(normalize_domain(d) for d in blocklist)
        return _state["package"]


def downloaded_domains() -> frozenset[str]:
    now = time.monotonic()
    with _lock:
        cached = _state.get("downloaded")
        if cached and now - cached[1] < conf.get("REFRESH_SECONDS"):
            return cached[0]
    from .models import Blocklist

    try:
        row = Blocklist.objects.filter(pk=1).values_list("domains", flat=True).first()
        domains = frozenset(d for d in (row or "").split() if d)
    except DatabaseError:
        domains = cached[0] if cached else frozenset()
    with _lock:
        _state["downloaded"] = (domains, now)
    return domains


def rules() -> tuple[frozenset[str], frozenset[str]]:
    """(blocked, allowed) domains set by hand in the admin."""
    now = time.monotonic()
    with _lock:
        cached = _state.get("rules")
        if cached and now - cached[2] < conf.get("RULES_REFRESH_SECONDS"):
            return cached[0], cached[1]
    from .models import DomainRule

    try:
        pairs = list(DomainRule.objects.filter(is_active=True).values_list("domain", "action"))
    except DatabaseError:
        pairs = []
    blocked = frozenset(d for d, a in pairs if a == DomainRule.BLOCK)
    allowed = frozenset(d for d, a in pairs if a == DomainRule.ALLOW)
    with _lock:
        _state["rules"] = (blocked, allowed, now)
    return blocked, allowed


def all_disposable_domains() -> frozenset[str]:
    return package_domains() | downloaded_domains()


# ── matching ─────────────────────────────────────────────────────────────


def domain_of(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return ""
    return normalize_domain(email.rpartition("@")[2])


def _candidates(domain: str):
    """``a.b.example.com`` -> itself, ``b.example.com``, ``example.com``."""
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        yield ".".join(parts[i:])


def _matches(domain: str, domains) -> bool:
    return any(c in domains for c in _candidates(domain))


def check_email(email: str, *, force: bool = False) -> Verdict:
    """Verdict for ``email``. With blocking switched off, never blocks (unless ``force``)."""
    domain = domain_of(email)
    if not force and not is_enabled():
        return Verdict(False, "", domain)
    if not domain or "." not in domain:
        return Verdict(True, INVALID, domain)
    blocked, allowed = rules()
    if _matches(domain, allowed):
        return Verdict(False, "", domain)
    if _matches(domain, blocked):
        return Verdict(True, BLOCKED, domain)
    if _matches(domain, all_disposable_domains()):
        return Verdict(True, DISPOSABLE, domain)
    return Verdict(False, "", domain)


def is_blocked_email(email: str) -> tuple[bool, str]:
    """House-compatible API: ``(blocked, reason)``."""
    verdict = check_email(email)
    return verdict.blocked, verdict.reason


def stats() -> dict:
    blocked, allowed = rules()
    return {
        "enabled": is_enabled(),
        "package": len(package_domains()),
        "downloaded": len(downloaded_domains()),
        "total": len(all_disposable_domains()),
        "blocked_by_hand": len(blocked),
        "allowed_by_hand": len(allowed),
    }
