# django-disposable-email

Block disposable and temporary email domains (mailinator, 10minutemail, ...)
when people sign up to your Django site, with first-class support for
django-allauth, including social logins. You can switch blocking on and off
with an environment variable, with a database flag in the admin, or with your
own server-configuration model.

- **Domain list:** the [disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains)
  list. The copy bundled with the PyPI package always applies; a daily download
  adds to it.
- **Downloads:** the downloaded list is stored in the database, so every
  process sees it and no restart is needed.
- **Download safety:** a download that fails, or has fewer than 1000 domains,
  keeps the previous list.
- **Subdomains:** `x.mailinator.com` is blocked because `mailinator.com` is.
- **Rules by hand in the admin:** block a domain, or allow one that the list
  gets wrong. A manual allow rule wins over everything else.
- **What it blocks with allauth:**
  - signup, add email and change email;
  - new accounts from Google, Apple, Microsoft and other providers, including
    auto-signup, which skips the forms.
- **What it leaves alone:** existing accounts keep logging in and resetting
  their passwords. Admin and `createsuperuser` are never blocked.
- **Audit:** every blocked attempt is stored with the email masked (`jo***@domain`).
  An `email_blocked` signal fires for your own alerts.
- **Wiring check:** a system check warns when an allauth form is not wired.

## Install

```bash
pip install "django-disposable-email[allauth,celery]"
```

```python
INSTALLED_APPS += ["disposable_email"]

DISPOSABLE_EMAIL = {
    "ENABLED": env.bool("DISPOSABLE_EMAIL_ENABLED", default=True),
}

# django-allauth: use the ready forms, or add DisposableEmailFormMixin FIRST
# in the bases of your own forms (see below).
ACCOUNT_FORMS = {
    "signup": "disposable_email.allauth.forms.SignupForm",
    "add_email": "disposable_email.allauth.forms.AddEmailForm",
    "change_email": "disposable_email.allauth.forms.ChangeEmailForm",
}
SOCIALACCOUNT_FORMS = {"signup": "disposable_email.allauth.social_forms.SocialSignupForm"}
```

```bash
python manage.py migrate
python manage.py update_disposable_domains     # first download
```

### Your own forms

```python
from allauth.account.forms import SignupForm
from disposable_email.allauth.forms import DisposableEmailFormMixin

class MySignupForm(DisposableEmailFormMixin, SignupForm):
    disposable_email_source = "signup"   # shown in the audit
```

Outside allauth (for example invitations or contact forms), use the validator:

```python
from disposable_email.validators import validate_not_disposable

email = forms.EmailField(validators=[validate_not_disposable])
```

Or call the check directly:

```python
from disposable_email.checks import check_email

verdict = check_email("someone@mailinator.com")
verdict.blocked, verdict.reason   # True, "disposable"  ("blocked" = admin rule)
```

## On / off

`ENABLED` accepts:

| Value | Where the switch lives |
|---|---|
| `True` / `False` | settings, usually from the environment |
| `"db"` | the admin, under «Disposable email › Configuration», a one-row table |
| `"myproject.flags.block_disposable"` | your own callable returning a bool, for example a field of your server-configuration model |

Values that come from the database or a callable are cached for 60 seconds in
each process (`ENABLED_CACHE_SECONDS`). If the callable raises, blocking stays
on. With blocking off, nothing is checked or audited.

## Daily update

Celery beat:

```python
CELERY_BEAT_SCHEDULE["disposable-email-update"] = {
    "task": "disposable_email.update_blocklist", "schedule": 86400.0,
}
```

`app.autodiscover_tasks()` finds it. If you pass an explicit list of apps,
include `"disposable_email"`.

Without Celery, use cron:

```
45 3 * * *  python manage.py update_disposable_domains
```

Other modes of the command:

- `--stats` prints the numbers without downloading.
- `--check someone@example.com` tells you what would happen to that address.

## Settings

All of them go under `DISPOSABLE_EMAIL`, and all are optional.

| Key | Default | Meaning |
|---|---|---|
| `ENABLED` | `True` | see above |
| `ENABLED_CACHE_SECONDS` | `60` | cache for `"db"` or callable switches |
| `SOURCES` | GitHub list | URLs to download, one domain per line |
| `INCLUDE_PACKAGE_LIST` | `True` | include the list bundled in `disposable-email-domains` |
| `MIN_DOMAINS` | `1000` | reject shorter downloads |
| `TIMEOUT` | `30` | download timeout in seconds |
| `REFRESH_SECONDS` | `3600` | how often each process re-reads the downloaded list |
| `RULES_REFRESH_SECONDS` | `300` | how often each process re-reads the admin rules |
| `LOG_ATTEMPTS` | `True` | store `BlockedAttempt` rows |
| `CLIENT_IP` | `None` | `"dotted.path"` to `callable(request)` returning the client IP; the default is `REMOTE_ADDR`, so set this behind a proxy |
| `MESSAGE` | built-in, translated (en, es) | text shown to the user |
| `CHECK_SOCIAL_SIGNUP` | `True` | block new social accounts with disposable emails |
| `SOCIAL_REDIRECT_URL` | `"account_login"` | where a blocked social signup is sent back to |
| `CHECK_ALLAUTH_WIRING` | `True` | run the system check `disposable_email.W001` |

## Why not the adapter's `clean_email`?

allauth also calls `DefaultAccountAdapter.clean_email` in two other places:

- **Password reset and login by code.** Blocking there would lock out existing
  users who have such an address.
- **Reading a social provider's email.** There a validation error is silently
  turned into "no email".

So this package hooks the forms that create or change an address, plus the
`pre_social_login` signal.

## Development

```bash
uv run pytest
```

MIT licence.
