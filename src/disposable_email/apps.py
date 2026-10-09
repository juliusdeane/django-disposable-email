from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DisposableEmailConfig(AppConfig):
    name = "disposable_email"
    verbose_name = _("Disposable email")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.apps import apps

        from . import system_checks  # noqa: F401  (registers the checks)

        if apps.is_installed("allauth.socialaccount"):
            from allauth.socialaccount.signals import pre_social_login

            from .allauth.receivers import block_disposable_social_signup

            pre_social_login.connect(block_disposable_social_signup,
                                     dispatch_uid="disposable_email.social_signup")
