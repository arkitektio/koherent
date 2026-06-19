"""Query-count regressions for the provenance read path.

effective_changes is an async resolver (it batches through a DataLoader), so
the schema is executed with async_to_sync. asgiref's thread_sensitive default
routes all sync ORM work back onto the calling thread, which keeps
django_assert_num_queries able to capture the queries.
"""

import strawberry
from asgiref.sync import async_to_sync
from strawberry.http.temporal_response import TemporalResponse
from strawberry_django.optimizer import DjangoOptimizerExtension

from kante.context import HttpContext, UniversalRequest
from test_project.schema import Query
from testing_module.models import MyModel

schema = strawberry.Schema(query=Query, extensions=[DjangoOptimizerExtension])

QUERY = """
query {
  myModels {
    provenance {
      id
      kind
      date
      user { sub }
      effectiveChanges { field oldValue newValue }
    }
  }
}
"""


def _context() -> HttpContext:
    return HttpContext(
        request=UniversalRequest(_extensions={}),
        response=TemporalResponse(),
        headers={},
    )


def _execute():
    return async_to_sync(schema.execute)(QUERY, context_value=_context())


def test_effective_changes_is_batched(db, django_assert_num_queries) -> None:
    """All of an instance's entries resolve from one sibling-history query."""
    model = MyModel.objects.create(your_field="a")
    for value in ("b", "c"):
        model.your_field = value
        model.save()

    # myModels + provenance prefetch + one sibling-history batch
    with django_assert_num_queries(3):
        result = _execute()

    assert result.errors is None
    assert result.data is not None
    entries = result.data["myModels"][0]["provenance"]
    assert len(entries) == 3

    # Meta ordering is -history_date: newest first
    assert entries[0]["kind"] == "UPDATE"
    assert entries[0]["effectiveChanges"] == [
        {"field": "your_field", "oldValue": "b", "newValue": "c"}
    ]
    assert entries[1]["effectiveChanges"] == [
        {"field": "your_field", "oldValue": "a", "newValue": "b"}
    ]
    # The creation entry has no previous record
    assert entries[-1]["kind"] == "CREATE"
    assert entries[-1]["effectiveChanges"] == []


def test_effective_changes_batched_across_instances(
    db, django_assert_num_queries
) -> None:
    """N selected instances must not mean N sibling-history queries."""
    for i in range(4):
        model = MyModel.objects.create(your_field=f"a{i}")
        model.your_field = f"b{i}"
        model.save()

    # myModels + provenance prefetch + ONE batched sibling-history
    # query covering all four instances
    with django_assert_num_queries(3):
        result = _execute()

    assert result.errors is None
    assert result.data is not None
    models = result.data["myModels"]
    assert len(models) == 4

    update_changes = []
    for entry_parent in models:
        entries = entry_parent["provenance"]
        assert [e["kind"] for e in entries] == ["UPDATE", "CREATE"]
        update_changes.extend(entries[0]["effectiveChanges"])
        assert entries[1]["effectiveChanges"] == []

    # Every instance's update was diffed against its own previous record.
    assert sorted(update_changes, key=lambda c: c["oldValue"]) == [
        {"field": "your_field", "oldValue": f"a{i}", "newValue": f"b{i}"}
        for i in range(4)
    ]
