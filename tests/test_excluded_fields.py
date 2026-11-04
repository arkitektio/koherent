"""A model's ``provenance_excluded_fields`` stay out of its history, next to the given ``excluded_fields``."""

from koherent.strawberry.types import _changes_for
from testing_module.models import CachedModel


def _entries(model: CachedModel) -> list:
    """The instance's history rows, oldest first."""
    return list(model.provenance_entries.order_by("history_date", "history_id"))


def test_a_change_to_an_excluded_column_records_no_change(db) -> None:
    """The derived and the given excluded columns never show up in a diff; a tracked one does."""
    model = CachedModel.objects.create(name="a", cache="x", note="n")
    model.cache = "y"
    model.note = "m"
    model.save()
    model.name = "b"
    model.cache = "z"
    model.save()

    first, second, third = _entries(model)

    assert _changes_for(second, first) == []
    assert [change.field for change in _changes_for(third, second)] == ["name"]


def test_a_history_row_reads_excluded_columns_from_the_live_row(db) -> None:
    """``instance`` of a history row still carries the excluded columns, as the row holds them now."""
    model = CachedModel.objects.create(name="a", cache="x", note="n")
    model.cache = "y"
    model.save()

    instance = _entries(model)[0].instance

    assert (instance.name, instance.cache, instance.note) == ("a", "y", "n")
