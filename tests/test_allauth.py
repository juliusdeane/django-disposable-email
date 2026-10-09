from types import SimpleNamespace

import pytest
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.core import checks as django_checks
from django.test import RequestFactory
from django.urls import reverse

from disposable_email.allauth.receivers import block_disposable_social_signup
from disposable_email.models import BlockedAttempt

pytestmark = pytest.mark.django_db


def signup(client, email):
    return client.post(reverse("account_signup"), {"email": email, "password1": "Very-l0ng-pass!"})


class TestForms:
    def test_signup_blocked_with_audit_and_ip(self, client):
        response = signup(client, "temp@mailinator.com")
        assert response.status_code == 200
        assert "not allowed" in response.content.decode()
        assert not get_user_model().objects.exists()
        attempt = BlockedAttempt.objects.get()
        assert (attempt.source, attempt.ip_address) == ("signup", "127.0.0.1")

    def test_signup_ok(self, client):
        assert signup(client, "ana@gmail.com").status_code == 302
        assert get_user_model().objects.filter(email="ana@gmail.com").exists()

    def test_switch_off(self, client, settings):
        settings.DISPOSABLE_EMAIL = {"ENABLED": False}
        assert signup(client, "temp@mailinator.com").status_code == 302

    def test_add_email_blocked(self, client):
        user = get_user_model().objects.create_user(username="ana", email="ana@gmail.com", password="x")
        client.force_login(user)
        response = client.post(reverse("account_email"), {"action_add": "", "email": "b@mailinator.com"})
        assert "not allowed" in response.content.decode()
        assert not EmailAddress.objects.filter(email="b@mailinator.com").exists()

    def test_existing_user_can_reset_password(self, client):
        """Legacy accounts with such an address are not locked out."""
        get_user_model().objects.create_user(username="old", email="old@mailinator.com", password="x")
        response = client.post(reverse("account_reset_password"), {"email": "old@mailinator.com"})
        assert response.status_code == 302
        assert not BlockedAttempt.objects.exists()

    def test_wiring_check(self, settings):
        assert not [e for e in django_checks.run_checks() if e.id.startswith("disposable_email")]
        settings.ACCOUNT_FORMS = {}
        ids = [e.id for e in django_checks.run_checks() if e.id.startswith("disposable_email")]
        assert ids.count("disposable_email.W001") == 3


def sociallogin(email, existing=False):
    return SimpleNamespace(is_existing=existing, user=SimpleNamespace(email=email),
                           email_addresses=[], account=SimpleNamespace(provider="google"))


def social_request():
    from django.contrib.messages.storage.fallback import FallbackStorage

    request = RequestFactory().get("/accounts/google/login/callback/")
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


class TestSocial:
    def test_new_social_account_blocked(self):
        with pytest.raises(ImmediateHttpResponse) as exc:
            block_disposable_social_signup(None, social_request(), sociallogin("x@mailinator.com"))
        assert exc.value.response["Location"] == reverse("account_login")
        assert BlockedAttempt.objects.get().source == "social:google"

    def test_existing_and_clean_accounts_pass(self):
        block_disposable_social_signup(None, social_request(), sociallogin("x@mailinator.com", existing=True))
        block_disposable_social_signup(None, social_request(), sociallogin("x@gmail.com"))
        assert not BlockedAttempt.objects.exists()

    def test_connected_to_the_allauth_signal(self):
        from allauth.socialaccount.signals import pre_social_login

        assert "disposable_email.social_signup" in str(pre_social_login.receivers)

    def test_can_be_disabled(self, settings):
        settings.DISPOSABLE_EMAIL = {"CHECK_SOCIAL_SIGNUP": False}
        block_disposable_social_signup(None, social_request(), sociallogin("x@mailinator.com"))
