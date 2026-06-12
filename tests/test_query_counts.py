"""Query-count regressions for the provenance read path.

Uses a sync schema (execute_sync) so django_assert_num_queries can capture
queries directly; the auth/koherent extensions only have async hooks and are
not needed for read-only queries.
"""

import strawberry
from strawberry.http.temporal_response import TemporalResponse
from strawberry_django.optimizer import DjangoOptimizerExtension

from kante.context import HttpContext, UniversalRequest
from test_project.schema import Query
from testing_module.models import MyModel

sync_schema = strawberry.Schema(query=Query, extensions=[DjangoOptimizerExtension])

QUERY = """
query {
  myModels {
    provenanceEntries {
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


def test_effective_changes_is_batched(db, django_assert_num_queries):
    model = MyModel.objects.create(your_field="a")
    for value in ("b", "c"):
        model.your_field = value
        model.save()

    # myModels + provenance_entries prefetch + one sibling-history batch
    with django_assert_num_queries(3):
        result = sync_schema.execute_sync(QUERY, context_value=_context())

    assert result.errors is None
    assert result.data is not None
    entries = result.data["myModels"][0]["provenanceEntries"]
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
