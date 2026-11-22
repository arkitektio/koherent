from typing import Any

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from simple_history.models import HistoricalRecords, HistoricForeignKey

from koherent.models import ProvenanceEntryModel

PROVENANCE_EXCLUDED_FIELDS = "provenance_excluded_fields"
"""The class attribute through which a model keeps its own columns out of its provenance.

A tuple of field names, usually declared once on an abstract base whose columns are derived
rather than changed by anyone (a cache the model recomputes on save)::

    class Described(models.Model):
        provenance_excluded_fields: ClassVar[tuple[str, ...]] = ("stored_descriptors",)

Every ``ProvenanceField`` on a subclass leaves these columns out of its history rows, and
so out of every diff, next to the ``excluded_fields`` it is given itself.
"""


class ProvenanceRecords(HistoricalRecords):
    """``HistoricalRecords`` that also leaves out what the model excludes from provenance."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Take ``HistoricalRecords``' arguments and keep the given exclusions apart."""
        super().__init__(*args, **kwargs)
        self.given_excluded_fields: list[str] = list(self.excluded_fields)

    def finalize(self, sender: type[models.Model], **kwargs: Any) -> None:
        """Build the history model with the model's own exclusions added to the given ones."""
        if sender is self.cls or (self.inherit and issubclass(sender, self.cls)):
            # A convention attribute any model may declare, not an attribute of every model.
            excluded: tuple[str, ...] = getattr(sender, PROVENANCE_EXCLUDED_FIELDS, ())
            # A new list per model: the history model keeps a reference to it
            # (``_history_excluded_fields``) to refill the excluded columns from the live row.
            given = self.given_excluded_fields
            self.excluded_fields = [
                *given,
                *(name for name in excluded if name not in given),
            ]
        super().finalize(sender, **kwargs)


def ProvenanceField(
    related_name: str = "provenance_entries",
    bases: list[type[models.Model]] | None = None,
    **kwargs: Any,
) -> HistoricalRecords:
    """Create a HistoricalRecords field whose history rows carry provenance.

    Every change to the model is recorded as a history row attributed to the
    client, user and (when present) Rekuest task it happened under.

    Columns named in ``excluded_fields`` or in the model's ``provenance_excluded_fields``
    (see :data:`PROVENANCE_EXCLUDED_FIELDS`) are not recorded.

    Args:
        related_name: Reverse accessor for the history rows on the model.
        bases: Extra abstract bases for the generated history model,
            appended after ProvenanceEntryModel.
        **kwargs: Passed through to simple_history.HistoricalRecords.
    """

    return ProvenanceRecords(
        bases=[ProvenanceEntryModel, *(bases or [])],
        related_name=related_name,
        **kwargs,
    )


__all__ = [
    "PROVENANCE_EXCLUDED_FIELDS",
    "GenericRelation",
    "HistoricForeignKey",
    "ProvenanceField",
    "ProvenanceRecords",
]
