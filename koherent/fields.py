from koherent.models import ProvenanceEntryModel
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from simple_history.models import HistoricalRecords, HistoricForeignKey
from typing import Any


def ProvenanceField(
    related_name: str = "provenance_entries",
    bases: list[type[models.Model]] | None = None,
    **kwargs: Any,
) -> HistoricalRecords:
    """Create a HistoricalRecords field whose history rows carry provenance.

    Every change to the model is recorded as a history row attributed to the
    client, user and (when present) Rekuest task it happened under.

    Args:
        related_name: Reverse accessor for the history rows on the model.
        bases: Extra abstract bases for the generated history model,
            appended after ProvenanceEntryModel.
        **kwargs: Passed through to simple_history.HistoricalRecords.
    """

    return HistoricalRecords(
        bases=[ProvenanceEntryModel, *(bases or [])],
        related_name=related_name,
        **kwargs,
    )


__all__ = [
    "ProvenanceField",
    "HistoricForeignKey",
    "GenericRelation",
]
