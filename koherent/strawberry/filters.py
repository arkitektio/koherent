"""Composable, semantic filter for the provenance of a model.

The intended use is as a drop-in for any model tracked by a
``koherent.fields.ProvenanceField``: inherit :class:`ProvenanceFilterMixin` into
the model's own ``filter_type`` and it gains a flat ``provenance`` filter that
traverses the history rows (and their task) of every instance.

    from koherent.strawberry import ProvenanceFilterMixin

    @strawberry_django.filter_type(MyModel)
    class MyModelFilter(ProvenanceFilterMixin):
        name: strawberry_django.filters.FilterLookup[str] | None

The exposed filter reads semantically and matches exactly, e.g.::

    myModels(filters: { provenance: { assignationId: "task-a", kind: CREATE } })

The reverse relation traversed is ``provenance_entries`` (the default
``related_name`` of ``ProvenanceField``); the mixin assumes the default.
"""

import datetime

import strawberry
import strawberry_django
from django.db.models import Q, QuerySet
from kante.types import Info
from strawberry_django.filters import filter_type, process_filters

from ..models import ProvenanceEntryModel
from .types import HistoryKind


@filter_type(ProvenanceEntryModel, description="Filter a model by its provenance.")
class ProvenanceFilter:
    """Flat, exact-match filter over a model's provenance entries (history rows).

    Bound to the abstract :class:`ProvenanceEntryModel`; every field is a
    ``filter_field`` resolving against each concrete history model at query time.
    The task attributes are lifted up so consumers never traverse a nested task.
    """

    @strawberry_django.filter_field(description="The assignation id the change ran under.")
    def assignation_id(self, value: str, prefix: str) -> Q:
        """Exact match against the task's assignation id."""
        return Q(**{f"{prefix}task__assignation_id": value})

    @strawberry_django.filter_field(description="The executing agent client id.")
    def agent_client_id(self, value: str, prefix: str) -> Q:
        """Exact match against the task's executing agent client id."""
        return Q(**{f"{prefix}task__agent_client_id": value})

    @strawberry_django.filter_field(description="The provenance issuer id.")
    def issuer(self, value: str, prefix: str) -> Q:
        """Exact match against the task's issuer id."""
        return Q(**{f"{prefix}task__issuer": value})

    @strawberry_django.filter_field(description="The sub of the user who made the change.")
    def changed_by(self, value: str, prefix: str) -> Q:
        """Exact match against the sub of the user who made the change."""
        return Q(**{f"{prefix}history_user__sub": value})

    @strawberry_django.filter_field(description="The kind of change.")
    def kind(self, value: HistoryKind, prefix: str) -> Q:
        """Match the change kind, mapping the enum to simple_history's code."""
        return Q(**{f"{prefix}history_type": value.value})

    @strawberry_django.filter_field(description="Only changes at or after this date.")
    def changed_since(self, value: datetime.datetime, prefix: str) -> Q:
        """Keep entries whose change date is at or after ``value``."""
        return Q(**{f"{prefix}history_date__gte": value})

    @strawberry_django.filter_field(description="Only changes at or before this date.")
    def changed_before(self, value: datetime.datetime, prefix: str) -> Q:
        """Keep entries whose change date is at or before ``value``."""
        return Q(**{f"{prefix}history_date__lte": value})


@strawberry.input(description="Filter a model by its provenance.")
class ProvenanceFilterMixin:
    """Drop-in mixin adding a flat ``provenance`` filter to a model's filter.

    Inherit it into a ``filter_type`` for any model tracked by a
    ``ProvenanceField`` to expose a ``provenance`` filter.
    """

    @strawberry_django.filter_field
    def provenance(
        self,
        value: ProvenanceFilter,
        prefix: str,
        queryset: QuerySet,
        info: Info,
    ) -> tuple[QuerySet, Q]:
        """Apply the nested provenance filter across the instance's history rows.

        Traversing the one-to-many ``provenance_entries`` relation joins one row
        per matching history entry, so ``distinct()`` keeps an instance from being
        returned once per matching entry.
        """
        queryset, q = process_filters(
            value,  # type: ignore[arg-type]  # ProvenanceFilter is a strawberry type at runtime
            queryset,
            info,
            prefix=f"{prefix}provenance_entries__",
        )
        return queryset.distinct(), q


__all__ = [
    "ProvenanceFilter",
    "ProvenanceFilterMixin",
]
