"""Settings, all under one dict::

    DISPOSABLE_EMAIL = {
        # True / False (e.g. from the environment), "db" (switch in the admin,
        # model disposable_email.Config) or "dotted.path.to.callable" returning
        # a bool (your own server-configuration model).
        "ENABLED": env.bool("DISPOSABLE_EMAIL_ENABLED", default=True),
    }

Every key is optional; see DEFAULTS.
"""

from django.conf import settings

GITHUB_URL = (
    "https://raw.githubusercontent.com/disposable-email-domains/"
    "disposable-email-domains/main/disposable_email_blocklist.conf"
)

DEFAULTS = {
    "ENABLED": True,
    # How long each process trusts an "ENABLED" value read from the DB/callable
    "ENABLED_CACHE_SECONDS": 60,
    # Lists downloaded by update_disposable_domains (plain text, one domain per line)
    "SOURCES": [GITHUB_URL],
    # Always include the list bundled in the disposable-email-domains package
    "INCLUDE_PACKAGE_LIST": True,
    # A download with fewer domains is rejected (the previous list is kept)
    "MIN_DOMAINS": 1000,
    "TIMEOUT": 30,
    # Each process re-reads the stored list / admin rules at most this often
    "REFRESH_SECONDS": 3600,
    "RULES_REFRESH_SECONDS": 300,
    # Store an audit row (masked email, domain, IP) for every blocked attempt
    "LOG_ATTEMPTS": True,
    # "dotted.path" to callable(request) -> client IP (default: REMOTE_ADDR)
    "CLIENT_IP": None,
    # Message shown to the user (None = built-in, translated)
    "MESSAGE": None,
    # Also block new accounts coming from social providers (django-allauth)
    "CHECK_SOCIAL_SIGNUP": True,
    # URL name to send a blocked social signup back to
    "SOCIAL_REDIRECT_URL": "account_login",
    # Run the system checks that verify the allauth wiring
    "CHECK_ALLAUTH_WIRING": True,
}


def get(name):
    user = getattr(settings, "DISPOSABLE_EMAIL", {}) or {}
    if name not in DEFAULTS:
        raise KeyError(name)
    return user.get(name, DEFAULTS[name])
