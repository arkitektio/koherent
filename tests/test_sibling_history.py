"""Unit tests for the batched effective-changes helpers in strawberry types."""

import datetime
from types import SimpleNamespace
from typing import Any

from asgiref.sync import async_to_sync
from django.utils import timezone

from kante.context import UniversalRequest
from koherent.strawberry.types import (
    _build_prev_maps,
    _fetch_effective_changes,
    _sibling_changes_loader,
)
from testing_module.models import MyModel

HistoryModel = MyModel().provenance_entries.model


def _info(request) -> Any:
    """A stand-in for strawberry's Info carrying just the request."""
    return SimpleNamespace(context=SimpleNamespace(request=request))


def _request() -> UniversalRequest:
    return UniversalRequest(_extensions={})


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

    _, prev_by_id = _build_prev_maps([first, second, third])

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

    _, prev_by_id = _build_prev_maps([first, second, third])

    assert prev_by_id[second.history_id].history_id == first.history_id
    assert prev_by_id[third.history_id].history_id == first.history_id
    # Parity with simple_history's own prev_record property.
    assert third.prev_record.history_id == first.history_id


def test_fetch_effective_changes_is_one_query_for_many_instances(
    db, django_assert_num_queries
) -> None:
    """All requested instances are diffed from a single sibling-history query."""
    models = []
    for i in range(3):
        model = MyModel.objects.create(your_field=f"a{i}")
        model.your_field = f"b{i}"
        model.save()
        models.append(model)

    with django_assert_num_queries(1):
        by_relation = _fetch_effective_changes(
            HistoryModel, [model.pk for model in models]
        )

    for i, model in enumerate(models):
        created, updated = _entries(model)
        changes = by_relation[model.pk]
        assert changes[created.history_id] == []
        (change,) = changes[updated.history_id]
        assert (change.field, change.old_value, change.new_value) == (
            "your_field",
            f"a{i}",
            f"b{i}",
        )


def test_loader_is_cached_per_request_and_per_key(
    db, django_assert_num_queries
) -> None:
    """One loader per request and model; repeated keys hit no database."""
    model = MyModel.objects.create(your_field="a")
    model.your_field = "b"
    model.save()
    first, second = _entries(model)

    request = _request()
    loader = _sibling_changes_loader(_info(request), HistoryModel)
    assert _sibling_changes_loader(_info(request), HistoryModel) is loader

    async def load():
        return await loader.load(model.pk)

    with django_assert_num_queries(1):
        changes = async_to_sync(load)()
    with django_assert_num_queries(0):
        assert async_to_sync(load)() == changes

    assert changes[first.history_id] == []
    (change,) = changes[second.history_id]
    assert (change.old_value, change.new_value) == ("a", "b")


def test_missing_request_degrades_to_ephemeral_loader(db) -> None:
    """Without a request the loader still resolves correctly, just uncached."""
    model = MyModel.objects.create(your_field="a")
    model.your_field = "b"
    model.save()
    first, second = _entries(model)

    loader = _sibling_changes_loader(_info(None), HistoryModel)
    assert _sibling_changes_loader(_info(None), HistoryModel) is not loader

    async def load():
        return await loader.load(model.pk)

    changes = async_to_sync(load)()

    assert changes[first.history_id] == []
    (change,) = changes[second.history_id]
    assert (change.old_value, change.new_value) == ("a", "b")


def test_unknown_relation_id_resolves_to_empty(db) -> None:
    """A relation id with no history rows loads an empty mapping."""
    loader = _sibling_changes_loader(_info(_request()), HistoryModel)

    async def load():
        return await loader.load(999999)

    assert async_to_sync(load)() == {}
