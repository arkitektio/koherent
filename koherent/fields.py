from koherent.models import ProvenanceEntryModel
from django.contrib.contenttypes.fields import GenericRelation
from simple_history.models import HistoricalRecords, HistoricForeignKey
from typing import Any


def ProvenanceField(**kwargs: Any) -> HistoricalRecords:
    """A shortcut to create a HistoricalRecords field.

    TODO: Strongly type this function.

    """

    return HistoricalRecords(
        bases=[ProvenanceEntryModel], related_name="provenance_entries", **kwargs
    )


__all__ = [
    "ProvenanceField",
    "HistoricForeignKey",
    "GenericRelation",
]
