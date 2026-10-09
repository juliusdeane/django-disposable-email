from django.dispatch import Signal

#: Sent for every blocked attempt.
#: kwargs: email, domain, reason ("disposable" | "blocked"), source, request (or None)
email_blocked = Signal()
