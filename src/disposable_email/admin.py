from django.contrib import admin

from .models import Blocklist, BlockedAttempt, Config, DomainRule


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    """On/off switch (only used with ``ENABLED = "db"``)."""

    list_display = ("__str__", "enabled", "updated_at")

    def has_add_permission(self, request):
        return not Config.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DomainRule)
class DomainRuleAdmin(admin.ModelAdmin):
    list_display = ("domain", "action", "reason", "is_active", "updated_at")
    list_editable = ("is_active",)
    list_filter = ("action", "is_active")
    search_fields = ("domain", "reason")


@admin.register(Blocklist)
class BlocklistAdmin(admin.ModelAdmin):
    list_display = ("count", "fetched_at")
    readonly_fields = ("count", "sources", "fetched_at")
    exclude = ("domains",)

    def has_add_permission(self, request):
        return False


@admin.register(BlockedAttempt)
class BlockedAttemptAdmin(admin.ModelAdmin):
    list_display = ("created_at", "email_masked", "domain", "reason", "source", "ip_address")
    list_filter = ("reason", "source")
    search_fields = ("domain", "email_masked")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
