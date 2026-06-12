from ..models import ProvenanceEntryModel, Task as TaskModel
import strawberry_django
import strawberry
from strawberry.scalars import JSON
from authentikate.strawberry.types import Client, Organization, User
from kante.types import Info
from enum import Enum
from typing import Any
import datetime


@strawberry.enum(description="The type of change that was made.")
class HistoryKind(str, Enum):
    """ The type of change that was made. """
    CREATE = "+"
    UPDATE = "~"
    DELETE = "-"


@strawberry.type(description="A change made to a model.")
class ModelChange:
    """The change made to a model."""
    field: str = strawberry.field(description="The field that was changed.")
    old_value: str | None = strawberry.field(description="The old value of the field.")
    new_value: str | None = strawberry.field(description="The new value of the field.")


@strawberry_django.type(
    TaskModel,
    pagination=True,
    description="A validated Rekuest task under which changes were made.",
)
class Task:
    """A validated Rekuest task under which changes were made."""

    id: strawberry.ID
    task_id: str = strawberry_django.field(description="The rekuest task id.")
    parent_id: str | None = strawberry_django.field(description="The parent task id, if any.")
    assigner: User | None = strawberry_django.field(description="The user that assigned the task.")
    assigner_sub: str = strawberry_django.field(description="The raw sub claim of the assigning user.")
    app: str = strawberry_django.field(description="The assigning app.")
    action: str = strawberry_django.field(description="The action hash.")
    args: JSON = strawberry_django.field(description="The arguments the task was assigned with.")
    organization: Organization = strawberry_django.field(description="The organization the task ran in.")
    created_at: datetime.datetime


def _sibling_history(info: Info, record: Any) -> tuple[dict, dict]:
    """Fetch all history rows of the record's instance once per request.

    Returns (rows_by_history_id, prev_by_history_id), where prev matches
    simple_history's prev_record semantics (strictly earlier history_date).
    Cached on the request so every sibling's effective_changes resolves
    from one query instead of one prev_record query per entry.
    """
    model = type(record)
    key = (model, record.history_relation_id)

    request = getattr(info.context, "request", None)
    extensions = getattr(request, "_extensions", None)
    store = (
        extensions.setdefault("koherent_sibling_history", {})
        if extensions is not None
        else {}
    )

    if key not in store:
        rows = model._default_manager.filter(
            history_relation_id=record.history_relation_id
        ).order_by("history_date", "history_id")

        rows_by_id: dict = {}
        prev_by_id: dict = {}
        group_date = None
        prev_of_group = None
        last = None
        for row in rows:
            if row.history_date != group_date:
                prev_of_group = last
                group_date = row.history_date
            rows_by_id[row.history_id] = row
            prev_by_id[row.history_id] = prev_of_group
            last = row
        store[key] = (rows_by_id, prev_by_id)

    return store[key]


@strawberry_django.type(ProvenanceEntryModel, pagination=True, description="A provenance event for a model.")
class ProvenanceEntry:
    """ A change made to a model."""
    client: Client | None
    task: Task | None = strawberry_django.field(
        description="The task during which the change occurred, if any."
    )
    user: User | None = strawberry_django.field(
        field_name="history_user", description="User who made the change."
    )
    kind: HistoryKind = strawberry_django.field(
        field_name="history_type", description="The type of change that was made."
    )
    date: datetime.datetime = strawberry_django.field(
        field_name="history_date", description="The date of the change."
    )
    id: strawberry.ID = strawberry_django.field(
        field_name="history_id", description="The ID of the history entry."
    )

    @strawberry_django.field(
        description="The effective changes made to the model.",
        only=["history_relation"],
    )
    def effective_changes(self, info: Info) -> list[ModelChange]:
        """This method returns the effective changes made to the model."""
        rows_by_id, prev_by_id = _sibling_history(info, self)
        # The cached row carries all columns, so diff_against never hits
        # deferred fields pruned by the optimizer's only().
        new_record = rows_by_id.get(self.history_id, self)  # type: ignore[attr-defined]
        old_record = prev_by_id.get(self.history_id)  # type: ignore[attr-defined]
        if old_record is None:
            return []

        delta = new_record.diff_against(old_record)
        return [
            ModelChange(field=change.field, old_value=change.old, new_value=change.new)
            for change in delta.changes
        ]
