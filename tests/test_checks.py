from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone, translation

from disposable_email import checks
from disposable_email.models import Blocklist, BlockedAttempt, Config, DomainRule
from disposable_email.signals import email_blocked
from disposable_email.updater import UpdateError, parse, update_blocklist
from disposable_email.validators import validate_not_disposable

pytestmark = pytest.mark.django_db


class TestMatching:
    def test_package_list(self):
        assert checks.check_email("a@mailinator.com") == checks.Verdict(True, "disposable", "mailinator.com")
        assert not checks.check_email("a@gmail.com")

    def test_subdomains_and_case(self):
        assert checks.check_email(" Someone@Mail.MAILINATOR.com. ").reason == "disposable"

    def test_invalid(self):
        assert checks.check_email("no-at-sign").reason == "invalid"

    def test_rules_block_and_allow(self):
        DomainRule.objects.create(domain="@Spam.example", reason="abuse")
        assert DomainRule.objects.get().domain == "spam.example"
        assert checks.check_email("x@spam.example").reason == "blocked"
        assert checks.check_email("x@eu.spam.example").reason == "blocked"
        DomainRule.objects.create(domain="mailinator.com", action="allow")
        assert not checks.check_email("x@mailinator.com")

    def test_inactive_and_deleted_rules(self):
        rule = DomainRule.objects.create(domain="spam.example")
        rule.is_active = False
        rule.save()
        assert not checks.check_email("x@spam.example")
        rule.is_active = True
        rule.save()
        assert checks.check_email("x@spam.example")
        rule.delete()
        assert not checks.check_email("x@spam.example")

    def test_other_processes_refresh_rules(self, settings):
        """A rule saved by ANOTHER process arrives after RULES_REFRESH_SECONDS."""
        settings.DISPOSABLE_EMAIL = {"RULES_REFRESH_SECONDS": 0}
        assert not checks.check_email("x@spam.example")
        DomainRule.objects.bulk_create([DomainRule(domain="spam.example")])  # no save(): no reset
        assert checks.check_email("x@spam.example").reason == "blocked"

    def test_compat_api(self):
        assert checks.is_blocked_email("a@mailinator.com") == (True, "disposable")


class TestSwitch:
    def test_setting_false(self, settings):
        settings.DISPOSABLE_EMAIL = {"ENABLED": False}
        assert not checks.check_email("a@mailinator.com")
        assert checks.check_email("a@mailinator.com", force=True)

    def test_db_flag(self, settings):
        settings.DISPOSABLE_EMAIL = {"ENABLED": "db"}
        assert checks.is_enabled()  # no row yet: on
        config = Config.load()
        config.enabled = False
        config.save()
        assert not checks.check_email("a@mailinator.com")
        Config.objects.update(enabled=True)  # another process: cached up to 60 s
        assert not checks.is_enabled()
        checks.reset_caches()
        assert checks.is_enabled()

    def test_callable(self, settings):
        settings.DISPOSABLE_EMAIL = {"ENABLED": "tests.conftest.flag_off"}
        assert not checks.is_enabled()
        checks.reset_caches()
        settings.DISPOSABLE_EMAIL = {"ENABLED": "tests.conftest.flag_on"}
        assert checks.is_enabled()

    def test_broken_callable_keeps_blocking(self, settings):
        settings.DISPOSABLE_EMAIL = {"ENABLED": "tests.conftest.flag_broken"}
        assert checks.is_enabled()

    def test_config_singleton(self):
        Config(enabled=False).save()
        Config(enabled=True).save()
        assert Config.objects.count() == 1


LIST = "\n".join(f"spam{i}.example" for i in range(1200)) + "\n# comment\n\nNEW-TEMP.example\n"


def fake_get(text, status=200):
    response = mock.Mock(status_code=status, text=text)
    response.raise_for_status = mock.Mock(side_effect=None if status == 200 else Exception("HTTP"))
    return mock.patch("requests.get", return_value=response)


class TestUpdate:
    def test_parse(self):
        assert parse("a.com\n# x\n b.org # c\nnot a domain\nlocalhost\n") == {"a.com", "b.org"}

    def test_download_is_stored_and_used(self):
        with fake_get(LIST):
            result = update_blocklist()
        assert result.count == 1201 and result.added == 1201
        assert Blocklist.objects.get().count == 1201
        assert checks.check_email("x@new-temp.example").reason == "disposable"

    def test_short_or_failed_download_keeps_previous(self):
        with fake_get(LIST):
            update_blocklist()
        with fake_get("tiny.example\n"), pytest.raises(UpdateError):
            update_blocklist()
        with fake_get("", status=500), pytest.raises(UpdateError):
            update_blocklist()
        assert Blocklist.objects.get().count == 1201

    def test_other_processes_pick_up_the_download(self, settings):
        settings.DISPOSABLE_EMAIL = {"REFRESH_SECONDS": 0}
        assert not checks.check_email("x@new-temp.example")
        Blocklist.objects.create(pk=1, domains="new-temp.example", count=1, fetched_at=timezone.now())
        assert checks.check_email("x@new-temp.example")

    def test_command(self, capsys):
        with fake_get(LIST):
            call_command("update_disposable_domains")
        out = capsys.readouterr().out
        assert "updated: 1201 domains" in out and "downloaded: 1201" in out
        call_command("update_disposable_domains", "--check", "a@mailinator.com")
        assert "blocked (disposable); blocking is on" in capsys.readouterr().out

    def test_celery_task(self):
        from disposable_email.tasks import update_blocklist as task

        with fake_get(LIST):
            task.apply()
        assert Blocklist.objects.get().count == 1201


class TestEnforce:
    def test_validator_audit_and_signal(self):
        received = []
        email_blocked.connect(lambda **kw: received.append(kw), weak=False, dispatch_uid="t")
        try:
            with pytest.raises(ValidationError) as error:
                validate_not_disposable("john.doe@mailinator.com")
        finally:
            email_blocked.disconnect(dispatch_uid="t")
        assert error.value.code == "disposable_email"
        attempt = BlockedAttempt.objects.get()
        assert attempt.email_masked == "jo***@mailinator.com"
        assert attempt.source == "validator"
        assert received[0]["reason"] == "disposable"
        validate_not_disposable("john@gmail.com")

    def test_spanish_message(self):
        with translation.override("es"):
            with pytest.raises(ValidationError) as error:
                validate_not_disposable("a@mailinator.com")
            assert "No se permiten direcciones de email temporales" in error.value.messages[0]

    def test_custom_message_and_no_audit(self, settings):
        settings.DISPOSABLE_EMAIL = {"MESSAGE": "Nope", "LOG_ATTEMPTS": False}
        with pytest.raises(ValidationError, match="Nope"):
            validate_not_disposable("a@mailinator.com")
        assert not BlockedAttempt.objects.exists()
