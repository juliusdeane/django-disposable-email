from django.db import models
from django.utils.translation import gettext_lazy as _


def normalize_domain(value: str) -> str:
    value = (value or "").strip().lower().rstrip(".")
    if "@" in value:
        value = value.rpartition("@")[2]
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError:
        return value


class Config(models.Model):
    """On/off switch in the database, used when ``ENABLED = "db"`` (one row)."""

    enabled = models.BooleanField(_("block disposable emails"), default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("configuration")
        verbose_name_plural = _("configuration")

    def __str__(self):
        return str(_("Enabled") if self.enabled else _("Disabled"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from .checks import reset_caches

        reset_caches()

    @classmethod
    def load(cls) -> "Config":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class DomainRule(models.Model):
    """Domain blocked or allowed by hand (wins over the downloaded list).

    Matches the domain and its subdomains: ``example.com`` also covers
    ``mail.example.com``.
    """

    BLOCK = "block"
    ALLOW = "allow"
    ACTIONS = [(BLOCK, _("Block")), (ALLOW, _("Allow"))]

    domain = models.CharField(_("domain"), max_length=253, unique=True,
                              help_text=_("Without @, e.g. example.com (covers its subdomains)"))
    action = models.CharField(_("action"), max_length=5, choices=ACTIONS, default=BLOCK)
    reason = models.CharField(_("reason"), max_length=255, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("domain rule")
        verbose_name_plural = _("domain rules")
        ordering = ["domain"]

    def __str__(self):
        return f"{self.get_action_display()} {self.domain}"

    def save(self, *args, **kwargs):
        self.domain = normalize_domain(self.domain)
        super().save(*args, **kwargs)
        from .checks import reset_caches

        reset_caches()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from .checks import reset_caches

        reset_caches()
        return result


class Blocklist(models.Model):
    """Last downloaded list (one row), shared by every process through the DB."""

    domains = models.TextField(_("domains"), blank=True, help_text=_("One per line"))
    count = models.PositiveIntegerField(_("number of domains"), default=0)
    sources = models.JSONField(_("sources"), default=list, blank=True)
    fetched_at = models.DateTimeField(_("downloaded at"))

    class Meta:
        verbose_name = _("downloaded list")
        verbose_name_plural = _("downloaded list")

    def __str__(self):
        return f"{self.count} @ {self.fetched_at:%Y-%m-%d %H:%M}"


class BlockedAttempt(models.Model):
    """Audit of blocked attempts. The email is stored masked (``jo***@domain``)."""

    email_masked = models.CharField(_("email"), max_length=254)
    domain = models.CharField(_("domain"), max_length=253, db_index=True)
    reason = models.CharField(_("reason"), max_length=20)
    source = models.CharField(_("where"), max_length=30, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.CharField(_("user agent"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("when"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("blocked attempt")
        verbose_name_plural = _("blocked attempts")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email_masked} ({self.reason})"
