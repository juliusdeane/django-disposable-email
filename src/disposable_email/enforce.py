"""What happens when an email is blocked: message, audit row and signal."""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

from . import conf
from .checks import Verdict, check_email
from .signals import email_blocked

logger = logging.getLogger("disposable_email")

DEFAULT_MESSAGE = _(
    "Disposable or temporary email addresses are not allowed. "
    "Please use a permanent email address."
)
ERROR_CODE = "disposable_email"


def message():
    return conf.get("MESSAGE") or DEFAULT_MESSAGE


def mask_email(email: str) -> str:
    local, _at, domain = (email or "").strip().partition("@")
    return f"{local[:2]}***@{domain}"[:254]


def client_ip(request) -> str | None:
    if request is None:
        return None
    path = conf.get("CLIENT_IP")
    if path:
        try:
            return import_string(path)(request) or None
        except Exception:  # noqa: BLE001
            logger.exception("disposable_email: CLIENT_IP callable failed")
    return request.META.get("REMOTE_ADDR") or None


def record_blocked(email: str, verdict: Verdict, *, request=None, source: str = "") -> None:
    """Log, store the audit row (masked) and send ``email_blocked``. Never raises."""
    logger.warning("disposable_email: blocked | reason=%s domain=%s source=%s",
                   verdict.reason, verdict.domain, source)
    if conf.get("LOG_ATTEMPTS"):
        try:
            from .models import BlockedAttempt

            BlockedAttempt.objects.create(
                email_masked=mask_email(email), domain=verdict.domain[:253],
                reason=verdict.reason, source=source[:30], ip_address=client_ip(request),
                user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:200],
            )
        except Exception:  # noqa: BLE001 — auditing must not break a signup
            logger.exception("disposable_email: could not store the audit row")
    try:
        email_blocked.send(sender=Verdict, email=email, domain=verdict.domain,
                           reason=verdict.reason, source=source, request=request)
    except Exception:  # noqa: BLE001
        logger.exception("disposable_email: email_blocked receiver failed")


def enforce(email: str, *, request=None, source: str = "") -> str:
    """Return ``email`` or raise ``ValidationError`` (code ``disposable_email``)."""
    verdict = check_email(email)
    if verdict.blocked and verdict.reason != "invalid":
        record_blocked(email, verdict, request=request, source=source)
        raise ValidationError(message(), code=ERROR_CODE)
    return email
