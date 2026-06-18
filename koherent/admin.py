from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from koherent.models import Task


class KoherentAdmin(SimpleHistoryAdmin):  # type: ignore
    """An admin class for Koherent models."""

    pass


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):  # type: ignore
    """Admin for persisted provenance assignations."""

    list_display = ("assignation_id", "assigner_sub", "agent_client_id", "organization", "created_at")
    list_select_related = ("organization",)
    search_fields = ("assignation_id", "assigner_sub", "caller_sub", "agent_sub", "agent_client_id")
    list_filter = ("organization",)
    raw_id_fields = ("assigner", "organization")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
