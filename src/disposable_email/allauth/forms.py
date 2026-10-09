from allauth.account import forms as account_forms

from ..enforce import enforce


def _request(form):
    request = getattr(form, "request", None)
    if request is None:
        try:
            from allauth.core import context

            request = context.request
        except Exception:  # noqa: BLE001
            request = None
    return request


class DisposableEmailFormMixin:
    """Put it FIRST in the bases of any allauth form with an ``email`` field."""

    disposable_email_source = "form"

    def clean_email(self):
        email = super().clean_email()
        if email:
            enforce(email, request=_request(self), source=self.disposable_email_source)
        return email


class SignupForm(DisposableEmailFormMixin, account_forms.SignupForm):
    disposable_email_source = "signup"


class AddEmailForm(DisposableEmailFormMixin, account_forms.AddEmailForm):
    disposable_email_source = "add_email"


class ChangeEmailForm(DisposableEmailFormMixin, account_forms.ChangeEmailForm):
    disposable_email_source = "change_email"
