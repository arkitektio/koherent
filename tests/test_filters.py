"""End-to-end tests for the composable provenance filter.

The MyModel query in test_project.schema inherits ProvenanceFilterMixin, so these
exercise the drop-in flat `provenance` filter the way a downstream consumer would:
filter a model by the provenance of its history, matching exactly.
"""

import pytest

from test_project.asgi import application
from kante.testing import GraphQLHttpTestClient

from tests.conftest import provenance_token


CREATE_MODEL = """
mutation($yourField: String!) {
    createModel(yourField: $yourField) { id }
}
"""

UPDATE_MODEL = """
mutation($id: ID!, $yourField: String!) {
    updateModel(id: $id, yourField: $yourField) { id }
}
"""

FILTER_MODELS = """
query($filters: MyModelFilter) {
    myModels(filters: $filters) { id yourField }
}
"""


async def create_model(headers: dict[str, str], your_field: str = "test") -> str:
    client = GraphQLHttpTestClient(application=application, headers=headers)
    answer = await client.execute(CREATE_MODEL, variables={"yourField": your_field})
    assert answer.get("data"), f"Expected data to be present {answer}"
    return answer["data"]["createModel"]["id"]


async def update_model(headers: dict[str, str], model_id: str, your_field: str) -> None:
    client = GraphQLHttpTestClient(application=application, headers=headers)
    answer = await client.execute(
        UPDATE_MODEL, variables={"id": model_id, "yourField": your_field}
    )
    assert answer.get("data"), f"Expected data to be present {answer}"


async def filter_models(headers: dict[str, str], filters: dict) -> list[dict]:
    client = GraphQLHttpTestClient(application=application, headers=headers)
    answer = await client.execute(FILTER_MODELS, variables={"filters": filters})
    assert answer.get("data"), f"Expected data to be present {answer}"
    return answer["data"]["myModels"]


def _task_headers(auth_headers: dict[str, str], tsk: str) -> dict[str, str]:
    """Auth headers carrying a signed provenance token for task ``tsk``."""
    return {**auth_headers, "Rekuest-Task": provenance_token(tsk=tsk)}


@pytest.mark.asyncio
async def test_filter_by_task_id(transactional_db, auth_headers) -> None:
    """Filtering by the task id returns only matching models."""
    a_id = await create_model(_task_headers(auth_headers, "task-a"), "a")
    await create_model(_task_headers(auth_headers, "task-b"), "b")

    matched = await filter_models(
        auth_headers, {"provenance": {"taskId": "task-a"}}
    )
    assert [m["id"] for m in matched] == [a_id]

    # A task that no model ran under yields nothing.
    none = await filter_models(
        auth_headers, {"provenance": {"taskId": "task-zzz"}}
    )
    assert none == []


@pytest.mark.asyncio
async def test_filter_by_task_id_is_exact(transactional_db, auth_headers) -> None:
    """The task id match is exact, not a substring search."""
    a_id = await create_model(_task_headers(auth_headers, "alpha-task"), "a")
    await create_model(_task_headers(auth_headers, "beta-task"), "b")

    # The exact id matches.
    matched = await filter_models(
        auth_headers, {"provenance": {"taskId": "alpha-task"}}
    )
    assert [m["id"] for m in matched] == [a_id]

    # A partial value does not.
    partial = await filter_models(
        auth_headers, {"provenance": {"taskId": "alpha"}}
    )
    assert partial == []


@pytest.mark.asyncio
async def test_filter_by_entry_kind(transactional_db, auth_headers) -> None:
    """Filtering by the entry kind distinguishes created-only from updated models."""
    headers = _task_headers(auth_headers, "task-kind")
    updated_id = await create_model(headers, "will-change")
    await create_model(headers, "stays")  # only ever has a CREATE entry
    await update_model(headers, updated_id, "changed")  # gains an UPDATE entry

    # Every model has a CREATE entry, so CREATE matches both.
    created = await filter_models(auth_headers, {"provenance": {"kind": "CREATE"}})
    assert len(created) == 2

    # Only the updated model has an UPDATE entry.
    changed = await filter_models(auth_headers, {"provenance": {"kind": "UPDATE"}})
    assert [m["id"] for m in changed] == [updated_id]


@pytest.mark.asyncio
async def test_filter_by_agent_client_id(transactional_db, auth_headers) -> None:
    """The task's agent client id is filterable through the drop-in path."""
    headers = {
        **auth_headers,
        "Rekuest-Task": provenance_token(tsk="task-cid", agent_cid="agent-7"),
    }
    target_id = await create_model(headers, "target")
    await create_model(_task_headers(auth_headers, "task-other"), "other")

    matched = await filter_models(
        auth_headers, {"provenance": {"agentClientId": "agent-7"}}
    )
    assert [m["id"] for m in matched] == [target_id]


@pytest.mark.asyncio
async def test_filter_returns_each_model_once(transactional_db, auth_headers) -> None:
    """Several matching history rows must not duplicate the model in the result.

    Filtering across the one-to-many provenance relation joins one row per
    matching entry; without distinct() the model would appear once per entry.
    """
    headers = _task_headers(auth_headers, "task-a")
    a_id = await create_model(headers, "v1")
    await update_model(headers, a_id, "v2")
    await update_model(headers, a_id, "v3")  # now three entries, all under task-a

    matched = await filter_models(
        auth_headers, {"provenance": {"taskId": "task-a"}}
    )
    assert [m["id"] for m in matched] == [a_id]


@pytest.mark.asyncio
async def test_filter_by_changed_by(transactional_db, auth_headers) -> None:
    """The user who made the change is filterable by their sub."""
    a_id = await create_model(auth_headers, "a")  # history_user is the static sub "1"

    matched = await filter_models(auth_headers, {"provenance": {"changedBy": "1"}})
    assert [m["id"] for m in matched] == [a_id]

    none = await filter_models(auth_headers, {"provenance": {"changedBy": "999"}})
    assert none == []


@pytest.mark.asyncio
async def test_filter_by_issuer(transactional_db, auth_headers) -> None:
    """The provenance issuer of the task is filterable."""
    a_id = await create_model(_task_headers(auth_headers, "task-iss"), "a")

    matched = await filter_models(auth_headers, {"provenance": {"issuer": "rekuest"}})
    assert [m["id"] for m in matched] == [a_id]

    none = await filter_models(auth_headers, {"provenance": {"issuer": "nope"}})
    assert none == []


@pytest.mark.asyncio
async def test_filter_by_changed_since_and_before(transactional_db, auth_headers) -> None:
    """The date predicates bound the change date in the right direction."""
    a_id = await create_model(auth_headers, "a")

    far_future = "2999-01-01T00:00:00+00:00"
    far_past = "2000-01-01T00:00:00+00:00"

    # Nothing changed after the far future.
    assert await filter_models(auth_headers, {"provenance": {"changedSince": far_future}}) == []
    # Everything changed before the far future.
    before = await filter_models(auth_headers, {"provenance": {"changedBefore": far_future}})
    assert [m["id"] for m in before] == [a_id]
    # Everything changed after the far past.
    since = await filter_models(auth_headers, {"provenance": {"changedSince": far_past}})
    assert [m["id"] for m in since] == [a_id]


@pytest.mark.asyncio
async def test_combined_predicates_match_same_entry(transactional_db, auth_headers) -> None:
    """Predicates in one provenance filter must be satisfied by the same entry."""
    a_id = await create_model(_task_headers(auth_headers, "task-a"), "a")  # CREATE under task-a
    await update_model(_task_headers(auth_headers, "task-b"), a_id, "b")  # UPDATE under task-b

    # No single entry is both under task-a AND an UPDATE.
    cross = await filter_models(
        auth_headers, {"provenance": {"taskId": "task-a", "kind": "UPDATE"}}
    )
    assert cross == []

    # The UPDATE entry is the one under task-b.
    matched = await filter_models(
        auth_headers, {"provenance": {"taskId": "task-b", "kind": "UPDATE"}}
    )
    assert [m["id"] for m in matched] == [a_id]


@pytest.mark.asyncio
async def test_filter_with_null_task_entries(transactional_db, auth_headers) -> None:
    """Entries created without a token (task is null) don't break task traversal."""
    untokened_id = await create_model(auth_headers, "untokened")  # entry.task is None
    tokened_id = await create_model(_task_headers(auth_headers, "task-a"), "tokened")

    # kind lives on the row itself, so both models match CREATE.
    created = await filter_models(auth_headers, {"provenance": {"kind": "CREATE"}})
    assert {m["id"] for m in created} == {untokened_id, tokened_id}

    # Traversing into the (null) task excludes the untokened model, doesn't crash.
    by_task = await filter_models(
        auth_headers, {"provenance": {"taskId": "task-a"}}
    )
    assert [m["id"] for m in by_task] == [tokened_id]
