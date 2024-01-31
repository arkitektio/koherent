from koherent.models import AppHistoryModel
from django.contrib.contenttypes.fields import GenericRelation
from simple_history.models import HistoricalRecords, HistoricForeignKey
from typing import Any


def HistoryField(**kwargs: Any) -> HistoricalRecords:
    """A shortcut to create a HistoricalRecords field.

    TODO: Strongly type this function.

    """

    return HistoricalRecords(
        bases=[AppHistoryModel], related_name="provenance", **kwargs
    )


__all__ = [
    "HistoryField",
    "HistoricForeignKey",
    "GenericRelation",
]
