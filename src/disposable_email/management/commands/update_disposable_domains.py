"""Download the disposable-domain lists (daily, from Celery beat or cron).

    manage.py update_disposable_domains             # download and store
    manage.py update_disposable_domains --stats     # only show numbers
    manage.py update_disposable_domains --check someone@example.com
"""

from django.core.management.base import BaseCommand, CommandError

from disposable_email import checks
from disposable_email.updater import UpdateError, update_blocklist


class Command(BaseCommand):
    help = "Download the disposable email domain lists and store them."

    def add_arguments(self, parser):
        parser.add_argument("--stats", action="store_true", help="Show numbers, do not download")
        parser.add_argument("--check", metavar="EMAIL", help="Tell whether an email would be blocked")

    def handle(self, *args, stats=False, check=None, **options):
        if check:
            verdict = checks.check_email(check, force=True)
            state = f"blocked ({verdict.reason})" if verdict.blocked else "allowed"
            switch = "on" if checks.is_enabled() else "off"
            self.stdout.write(f"{check}: {state}; blocking is {switch}")
            return
        if not stats:
            try:
                result = update_blocklist()
            except UpdateError as exc:
                raise CommandError(f"update failed, previous list kept: {exc}") from exc
            self.stdout.write(f"updated: {result.count} domains (+{result.added} -{result.removed})")
        for key, value in checks.stats().items():
            self.stdout.write(f"{key}: {value}")
