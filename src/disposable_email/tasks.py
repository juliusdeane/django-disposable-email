"""Celery task (optional: only if Celery is installed).

Schedule ``disposable_email.update_blocklist`` once a day in Celery beat. Without
Celery, run ``manage.py update_disposable_domains`` from cron.
"""

try:
    from celery import shared_task
except ImportError:  # pragma: no cover
    shared_task = None

if shared_task is not None:

    @shared_task(name="disposable_email.update_blocklist", bind=True, max_retries=3,
                 default_retry_delay=600, ignore_result=True)
    def update_blocklist(self):
        from .updater import UpdateError, update_blocklist as run

        try:
            run()
        except UpdateError as exc:
            raise self.retry(exc=exc)
