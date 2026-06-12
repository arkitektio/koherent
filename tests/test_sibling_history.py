"""Unit tests for the per-request sibling-history batching in strawberry types."""

import datetime
from types import SimpleNamespace

from django.utils import timezone

from koherent.strawberry.types import _sibling_history
from testing_module.models import MyModel


def _info(request) -> SimpleNamespace:
    return SimpleNamespace(context=SimpleNamespace(request=request))


def _request() -> SimpleNamespace:
    return SimpleNamespace(_extensions={})


def _entries(model: MyModel) -> list:
    """The instance's history rows, oldest first."""
    return list(model.provenance_entries.order_by("history_date", "history_id"))


def test_prev_records_paired_like_simple_history(db) -> None:
    """Each row maps to the strictly earlier row, matching prev_record."""
    model = MyModel.objects.create(your_field="a")
    for value in ("b", "c"):
        model.your_field = value
        model.save()
    first, second, third = _entries(model)

    _, prev_by_id = _sibling_history(_info(_request()), third)

    assert prev_by_id[first.history_id] is None
    assert prev_by_id[second.history_id].history_id == first.history_id
    assert prev_by_id[third.history_id].history_id == second.history_id
    # Parity with simple_history's own prev_record property.
    assert third.prev_record.history_id == second.history_id


def test_tied_history_dates_share_the_strictly_earlier_prev(db) -> None:
    """Rows with identical history_date all pair with the last earlier row.

    prev_record filters on history_date__lt, so within a timestamp tie the
    previous record is the last row strictly before the tie, never a sibling
    inside it.
    """
    model = MyModel.objects.create(your_field="a")
    for value in ("b", "c"):
        model.your_field = value
        model.save()
    first, second, third = _entries(model)

    tie = timezone.now() + datetime.timedelta(seconds=10)
    model.provenance_entries.filter(
        history_id__in=[second.history_id, third.history_id]
    ).update(history_date=tie)
    first, second, third = _entries(model)

    _, prev_by_id = _sibling_history(_info(_request()), third)

    assert prev_by_id[second.history_id].history_id == first.history_id
    assert prev_by_id[third.history_id].history_id == first.history_id
    # Parity with simple_history's own prev_record property.
    assert third.prev_record.history_id == first.history_id


def test_sibling_history_is_cached_per_request(db, django_assert_num_queries) -> None:
    """A second lookup through the same request store hits no database."""
    model = MyModel.objects.create(your_field="a")
    model.your_field = "b"
    model.save()
    first, second = _entries(model)

    request = _request()
    with django_assert_num_queries(1):
        _sibling_history(_info(request), second)
    with django_assert_num_queries(0):
        _, prev_by_id = _sibling_history(_info(request), first)

    assert prev_by_id[second.history_id].history_id == first.history_id


def test_missing_request_degrades_to_uncached_lookup(db) -> None:
    """Without a request store the helper still pairs records correctly."""
    model = MyModel.objects.create(your_field="a")
    model.your_field = "b"
    model.save()
    first, second = _entries(model)

    _, prev_by_id = _sibling_history(_info(None), second)

    assert prev_by_id[first.history_id] is None
    assert prev_by_id[second.history_id].history_id == first.history_id
