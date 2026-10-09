"""System checks: is the allauth wiring complete?"""

from django.apps import apps
from django.conf import settings
from django.core import checks
from django.utils.module_loading import import_string

from . import conf

FORMS = {
    "ACCOUNT_FORMS": ("allauth.account", ["signup", "add_email", "change_email"]),
    "SOCIALACCOUNT_FORMS": ("allauth.socialaccount", ["signup"]),
}


@checks.register(checks.Tags.security)
def check_allauth_forms(app_configs=None, **kwargs):
    if not conf.get("CHECK_ALLAUTH_WIRING"):
        return []
    errors = []
    for setting, (app, names) in FORMS.items():
        if not apps.is_installed(app):
            continue
        from .allauth.forms import DisposableEmailFormMixin

        configured = getattr(settings, setting, {}) or {}
        for name in names:
            path = configured.get(name)
            try:
                form = import_string(path) if path else None
            except ImportError:
                continue  # Django/allauth report it
            if form is None or not issubclass(form, DisposableEmailFormMixin):
                errors.append(checks.Warning(
                    f"{setting}['{name}'] does not block disposable emails.",
                    hint="Use disposable_email.allauth.forms (or social_forms) or add "
                         "DisposableEmailFormMixin first in the form's bases.",
                    id="disposable_email.W001",
                ))
    value = conf.get("ENABLED")
    if value == "db" and not apps.is_installed("disposable_email"):
        errors.append(checks.Error("ENABLED='db' needs 'disposable_email' in INSTALLED_APPS",
                                   id="disposable_email.E001"))
    return errors
