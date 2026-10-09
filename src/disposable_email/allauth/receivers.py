"""Social signups: block NEW accounts whose provider email is disposable."""

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url

from .. import conf
from ..checks import INVALID, check_email
from ..enforce import message, record_blocked


def _emails(sociallogin):
    primary = getattr(sociallogin.user, "email", "") or ""
    if primary:
        return [primary]
    return [a.email for a in getattr(sociallogin, "email_addresses", []) if a.email]


def block_disposable_social_signup(sender, request, sociallogin, **kwargs):
    if not conf.get("CHECK_SOCIAL_SIGNUP") or sociallogin.is_existing:
        return
    from allauth.core.exceptions import ImmediateHttpResponse

    for email in _emails(sociallogin):
        verdict = check_email(email)
        if verdict.blocked and verdict.reason != INVALID:
            provider = getattr(sociallogin.account, "provider", "")
            record_blocked(email, verdict, request=request, source=f"social:{provider}"[:30])
            messages.error(request, message(), fail_silently=True)
            raise ImmediateHttpResponse(HttpResponseRedirect(resolve_url(conf.get("SOCIAL_REDIRECT_URL"))))
