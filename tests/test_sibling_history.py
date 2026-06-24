"""Unit tests for the batched effective-changes helpers in strawberry types."""

import datetime
from types import SimpleNamespace
from typing import Any

from asgiref.sync import async_to_sync
from django.utils import timezone

from kante.context import UniversalRequest
from koherent.strawberry.types import (
    _build_prev_maps,
    _changes_for,
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


def test_build_prev_maps_empty_and_single_row() -> None:
    """Boundary inputs: an empty history and a lone row pair correctly."""
    assert _build_prev_maps([]) == ({}, {})

    row = SimpleNamespace(history_id=1, history_date=timezone.now())
    rows_by_id, prev_by_id = _build_prev_maps([row])
    assert rows_by_id == {1: row}
    assert prev_by_id == {1: None}


def test_changes_for_stringifies_non_string_values() -> None:
    """diff_against values of any type become strings; None stays null.

    The is-None check (not a falsy check) must keep False as "False" rather than
    dropping it to null.
    """
    delta = SimpleNamespace(
        changes=[
            SimpleNamespace(field="count", old=1, new=2),
            SimpleNamespace(field="flag", old=False, new=True),
            SimpleNamespace(field="note", old=None, new="hi"),
        ]
    )
    new_record = SimpleNamespace(diff_against=lambda _old: delta)

    changes = {c.field: c for c in _changes_for(new_record, object())}

    assert (changes["count"].old_value, changes["count"].new_value) == ("1", "2")
    assert (changes["flag"].old_value, changes["flag"].new_value) == ("False", "True")
    assert (changes["note"].old_value, changes["note"].new_value) == (None, "hi")


def test_changes_for_json_fields_preserve_native_types() -> None:
    """The *_json fields keep native value types; None stays null.

    JSON-native values (numbers, booleans, dicts) pass through unchanged, while
    non-serializable values (datetime, ...) fall back to a string.
    """
    when = timezone.now()
    delta = SimpleNamespace(
        changes=[
            SimpleNamespace(field="count", old=1, new=2),
            SimpleNamespace(field="flag", old=False, new=True),
            SimpleNamespace(field="note", old=None, new="hi"),
            SimpleNamespace(field="payload", old=None, new={"k": 1}),
            SimpleNamespace(field="created_at", old=None, new=when),
        ]
    )
    new_record = SimpleNamespace(diff_against=lambda _old: delta)

    changes = {c.field: c for c in _changes_for(new_record, object())}

    assert (changes["count"].old_value_json, changes["count"].new_value_json) == (1, 2)
    assert changes["flag"].old_value_json is False
    assert changes["flag"].new_value_json is True
    assert (changes["note"].old_value_json, changes["note"].new_value_json) == (None, "hi")
    assert changes["payload"].new_value_json == {"k": 1}
    # datetime is not JSON-native, so it falls back to its string form.
    assert changes["created_at"].new_value_json == str(when)
