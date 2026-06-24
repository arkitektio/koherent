from ..models import ProvenanceEntryModel, Task as TaskModel
import strawberry_django
import strawberry
from strawberry.dataloader import DataLoader
from strawberry.scalars import JSON
from asgiref.sync import sync_to_async
from authentikate.strawberry.types import Client, Organization, User
from kante.types import Info
from collections import defaultdict
from django.db import models
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
    old_value_json: JSON | None = strawberry.field(
        description="The old value of the field, preserving its native JSON type."
    )
    new_value_json: JSON | None = strawberry.field(
        description="The new value of the field, preserving its native JSON type."
    )


@strawberry_django.type(
    TaskModel,
    pagination=True,
    description="A verified provenance task under which changes were made.",
)
class Task:
    """A verified provenance task under which changes were made."""

    id: strawberry.ID
    task_id: str = strawberry_django.field(description="This task id.")
    parent_task_id: str | None = strawberry_django.field(
        description="The immediate parent task id, if any."
    )
    root_task_id: str = strawberry_django.field(
        description="The root task id of the whole causal tree."
    )
    assigner: User | None = strawberry_django.field(description="The root human causer.")
    assigner_sub: str = strawberry_django.field(description="The raw root human causer sub.")
    caller_sub: str = strawberry_django.field(description="The immediate causer of this hop.")
    agent_sub: str = strawberry_django.field(description="The executing agent user sub.")
    agent_client_id: str = strawberry_django.field(description="The executing agent client id.")
    issuer: str = strawberry_django.field(description="The provenance issuer id.")
    token_id: str = strawberry_django.field(description="The unique single-use token id.")
    args_hash: str = strawberry_django.field(description="The SHA-256 of the canonicalized args.")
    args_hash_algorithm: str = strawberry_django.field(
        description="The args canonicalization algorithm/version."
    )
    organization: Organization = strawberry_django.field(description="The organization the task ran in.")
    created_at: datetime.datetime


_LOADER_EXTENSION_KEY = "koherent_sibling_history_loaders"

# {history_id: effective changes of that entry} for one instance.
ChangesByHistoryId = dict[Any, list[ModelChange]]


def _build_prev_maps(rows: list[Any]) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """Pair each history row with its previous record.

    `rows` must hold one instance's history ordered by (history_date,
    history_id). Returns (rows_by_history_id, prev_by_history_id), where prev
    matches simple_history's prev_record semantics: the last row with a
    strictly earlier history_date, so rows tied on a timestamp share a prev.
    """
    rows_by_id: dict[Any, Any] = {}
    prev_by_id: dict[Any, Any] = {}
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
    return rows_by_id, prev_by_id


_JSON_NATIVE = (str, int, float, bool, type(None))


def _to_json_safe(value: Any) -> Any:
    """Coerce a raw history field value to something the JSON scalar can encode.

    Native JSON types (and nested dict/list of them) pass through; anything else
    (datetime, Decimal, UUID, model instances, ...) falls back to str(), since
    strawberry's JSON scalar serializes through the stdlib JSON encoder.
    """
    if isinstance(value, _JSON_NATIVE):
        return value
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return str(value)


def _changes_for(new_record: Any, old_record: Any | None) -> list[ModelChange]:
    """Diff a history row against its previous record."""
    if old_record is None:
        return []
    delta = new_record.diff_against(old_record)
    return [
        ModelChange(
            field=change.field,
            # diff_against yields the raw field values (ints, datetimes, fk ids,
            # ...); stringify them to match the str | None GraphQL fields, keeping
            # None as null rather than the literal "None". The *_json fields keep
            # the native value via _to_json_safe for type-faithful consumers.
            old_value=None if change.old is None else str(change.old),
            new_value=None if change.new is None else str(change.new),
            old_value_json=None if change.old is None else _to_json_safe(change.old),
            new_value_json=None if change.new is None else _to_json_safe(change.new),
        )
        for change in delta.changes
    ]


def _fetch_effective_changes(
    model: type[models.Model], relation_ids: list[Any]
) -> dict[Any, ChangesByHistoryId]:
    """Compute the effective changes of every requested instance in one query.

    Loads the full history of each instance (computing prev pairs and
    full-column diffs needs every row), so memory grows with history length.

    Sync only: diff_against may itself query for m2m-tracked fields, so the
    diffing must stay inside the loader's sync_to_async hop.
    """
    rows = model._default_manager.filter(
        history_relation_id__in=relation_ids
    ).order_by("history_relation_id", "history_date", "history_id")

    grouped: dict[Any, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[row.history_relation_id].append(row)

    result: dict[Any, ChangesByHistoryId] = {}
    for relation_id, instance_rows in grouped.items():
        rows_by_id, prev_by_id = _build_prev_maps(instance_rows)
        result[relation_id] = {
            history_id: _changes_for(row, prev_by_id[history_id])
            for history_id, row in rows_by_id.items()
        }
    return result


def _sibling_changes_loader(info: Info, model: type[models.Model]) -> DataLoader:
    """The request's effective-changes DataLoader for one history model.

    Keyed by history_relation_id, the loader batches all instances selected
    in the operation into a single sibling-history query (its per-key cache
    also deduplicates entries of the same instance). Loaders are stored on
    the request so they live exactly one request; without a request an
    ephemeral loader still resolves correctly, just uncached.
    """
    request = getattr(info.context, "request", None)
    loaders: dict[type[models.Model], DataLoader] = {}
    if request is not None:
        try:
            loaders = request.get_extension(_LOADER_EXTENSION_KEY)
        except ValueError:
            request.set_extension(_LOADER_EXTENSION_KEY, loaders)

    if model not in loaders:
        fetch = sync_to_async(_fetch_effective_changes)

        async def load_fn(
            keys: list[Any], *, _model: type[models.Model] = model
        ) -> list[ChangesByHistoryId]:
            by_relation = await fetch(_model, list(keys))
            return [by_relation.get(key, {}) for key in keys]

        loaders[model] = DataLoader(load_fn=load_fn)
    return loaders[model]


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
    async def effective_changes(self, info: Info) -> list[ModelChange]:
        """The effective changes made to the model.

        Batched: every entry selected in the operation resolves from one
        sibling-history query per history model. The loader's rows carry all
        columns, so diff_against never hits deferred fields pruned by the
        optimizer's only().
        """
        # At runtime self is a row of the generated history model.
        loader = _sibling_changes_loader(info, type(self))  # type: ignore[arg-type]
        changes_by_history_id = await loader.load(self.history_relation_id)  # type: ignore[attr-defined]
        return changes_by_history_id.get(self.history_id, [])  # type: ignore[attr-defined]
