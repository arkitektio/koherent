from django.conf import settings
from django.db import models
from authentikate.models import Client


class Task(models.Model):
    """A verified provenance task under which changes were made.

    One row per task, created lazily the first time a change happens
    under it (see `koherent.utils.get_or_create_task`). The data comes from a
    signature-verified provenance token (`authentikate.provenance.ProvenanceToken`)
    that AuthentikateExtension attached to the request.
    """

    task_id = models.CharField(
        max_length=1000, unique=True, help_text="This task id (provenance tsk)."
    )
    parent_task_id = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        help_text="The immediate parent task id, if any.",
    )
    root_task_id = models.CharField(
        max_length=1000, help_text="The root task id of the whole causal tree."
    )
    assigner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        help_text="The root human causer (resolved from the rcb claim).",
    )
    assigner_sub = models.CharField(
        max_length=1000, help_text="The raw root human causer sub (rcb claim)."
    )
    caller_sub = models.CharField(
        max_length=1000, help_text="The immediate causer of this hop (sub claim)."
    )
    agent_sub = models.CharField(
        max_length=1000, help_text="The executing agent user sub (act.sub claim)."
    )
    agent_client_id = models.CharField(
        max_length=1000, help_text="The executing agent OAuth client id (act.cid claim)."
    )
    issuer = models.CharField(
        max_length=1000, help_text="The provenance issuer id (iss claim)."
    )
    token_id = models.CharField(
        max_length=1000, unique=True, help_text="The unique single-use token id (jti claim)."
    )
    args_hash = models.CharField(
        max_length=1000, help_text="The SHA-256 of the canonicalized args (ahs claim)."
    )
    args_hash_algorithm = models.CharField(
        max_length=200, help_text="The args canonicalization algorithm/version (aha claim)."
    )
    organization = models.ForeignKey(
        "authentikate.Organization",
        on_delete=models.CASCADE,
        related_name="tasks",
        help_text="The organization the task ran in",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        """ A human readable representation of the task, useful in admin and debugging. """
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
        """ This is an abstract base model, not a real table. It provides common fields and behavior for all history models. """
        abstract = True
        ordering = ["-history_date"]


from .signals import add_history_app  # noqa: E402

__all__ = [
    "ProvenanceEntryModel",
    "Task",
    "add_history_app",
]
