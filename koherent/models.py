from django.conf import settings
from django.db import models
from authentikate.models import Client


class Task(models.Model):
    """A validated Rekuest task under which changes were made.

    One row per task id, created lazily the first time a change happens
    during that task (see `koherent.utils.get_or_create_task`). The payload
    comes from the Rekuest task header, validated by authentikate against
    the request's token.
    """

    task_id = models.CharField(max_length=1000, unique=True, help_text="The rekuest task id")
    parent_id = models.CharField(max_length=1000, null=True, blank=True, help_text="The parent task id, if any")
    assigner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        help_text="The user that assigned the task (resolved from the sub claim)",
    )
    assigner_sub = models.CharField(max_length=1000, help_text="The raw sub claim of the assigning user")
    app = models.CharField(max_length=1000, help_text="The assigning app")
    action = models.CharField(max_length=1000, help_text="The action hash")
    args = models.JSONField(default=dict, blank=True, help_text="The arguments the task was assigned with")
    organization = models.ForeignKey(
        "authentikate.Organization",
        on_delete=models.CASCADE,
        related_name="tasks",
        help_text="The organization the task ran in",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Task {self.task_id}"


class ProvenanceEntryModel(models.Model):
    """
    Abstract base mixed into every history model, attributing each change
    to the client and (when present) the task it happened under.
    """

    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The task during which the change occurred, if any",
    )

    class Meta:
        abstract = True
        ordering = ["-history_date"]


from .signals import add_history_app  # noqa: E402

__all__ = [
    "ProvenanceEntryModel",
    "Task",
    "add_history_app",
]
