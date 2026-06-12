from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from koherent.models import Task


class KoherentAdmin(SimpleHistoryAdmin):  # type: ignore
    """An admin class for Koherent models."""

    pass


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):  # type: ignore
    """Admin for persisted Rekuest tasks."""

    list_display = ("task_id", "assigner_sub", "app", "action", "organization", "created_at")
    search_fields = ("task_id", "assigner_sub", "app", "action")
    list_filter = ("organization",)
