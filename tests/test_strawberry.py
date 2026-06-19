"""End-to-end tests for provenance and task tracking over HTTP."""

import pytest
from asgiref.sync import sync_to_async

from test_project.asgi import application
from kante.testing import GraphQLHttpTestClient

from authentikate.models import Membership, Organization, User
from koherent.models import Task
from tests.conftest import provenance_token


CREATE_MODEL = """
mutation($yourField: String!) {
    createModel(yourField: $yourField) {
        id
        provenance {
            id
            kind
            effectiveChanges { field oldValue newValue }
            task {
                assignationId
                assignerSub
                callerSub
                agentSub
                agentClientId
                tokenId
            }
        }
    }
}
"""


GET_MODEL = """
query($id: ID!) {
    myModel(id: $id) {
        id
        yourField
        provenance {
            id
            kind
            effectiveChanges { field oldValue newValue }
            task {
                assignationId
                assignerSub
                callerSub
                agentSub
                agentClientId
                tokenId
            }
        }
    }
}
"""


async def create_model(headers: dict[str, str], your_field: str = "test") -> dict:
    client = GraphQLHttpTestClient(application=application, headers=headers)
    answer = await client.execute(CREATE_MODEL, variables={"yourField": your_field})
    assert answer.get("data"), f"Expected data to be present {answer}"
    return answer["data"]["createModel"]


async def get_model(headers: dict[str, str], model_id: str) -> dict:
    client = GraphQLHttpTestClient(application=application, headers=headers)
    answer = await client.execute(GET_MODEL, variables={"id": model_id})
    assert answer.get("data"), f"Expected data to be present {answer}"
    return answer["data"]["myModel"]


@pytest.mark.asyncio
async def test_create_without_task(transactional_db, auth_headers) -> None:
    """Without a task header nothing is persisted and the entry has no task."""
    created = await create_model(auth_headers)

    assert created["id"] is not None
    entry = created["provenance"][0]
    assert entry["kind"] == "CREATE"
    # The creation entry has no previous record to diff against.
    assert entry["effectiveChanges"] == []
    assert entry["task"] is None
    assert await sync_to_async(Task.objects.count)() == 0


@pytest.mark.asyncio
async def test_task_created(transactional_db, task_headers) -> None:
    """A verified provenance token creates one task row linked from the history entry."""
    created = await create_model(task_headers)

    entry = created["provenance"][0]
    assert entry["task"] is not None
    assert entry["task"]["assignationId"] == "task-1"
    assert entry["task"]["assignerSub"] == "1"
    assert entry["task"]["callerSub"] == "1"
    assert entry["task"]["agentSub"] == "1"
    assert entry["task"]["agentClientId"] == "static"

    def check_row() -> None:
        task = Task.objects.get(assignation_id="task-1")
        assert task.root_assignation_id == "task-1"
        assert task.organization.slug == "static_org"
        assert task.assigner is not None
        assert task.assigner.sub == "1"

    await sync_to_async(check_row)()


@pytest.mark.asyncio
async def test_task_reused(transactional_db, task_headers) -> None:
    """Several changes during the same task share a single task row."""
    await create_model(task_headers, "first")
    await create_model(task_headers, "second")

    assert await sync_to_async(Task.objects.count)() == 1


@pytest.mark.asyncio
async def test_cross_user_assigner(transactional_db, auth_headers) -> None:
    """A root human causer (rcb) other than the agent resolves to that user's row."""

    def seed() -> None:
        org, _ = Organization.objects.get_or_create(slug="static_org")
        assigner, _ = User.objects.get_or_create(
            sub="2", iss="static_issuer", defaults={"username": "static_issuer_2"}
        )
        Membership.objects.get_or_create(user=assigner, organization=org)

    await sync_to_async(seed)()

    headers = {**auth_headers, "Rekuest-Task": provenance_token(tsk="task-2", rcb="2")}
    await create_model(headers)

    def check_row() -> None:
        task = Task.objects.get(assignation_id="task-2")
        assert task.assigner is not None
        assert task.assigner.sub == "2"
        assert task.assigner_sub == "2"

    await sync_to_async(check_row)()


@pytest.mark.asyncio
async def test_provenance_survives_create_then_query(transactional_db, task_headers) -> None:
    """A model created under a task exposes the same provenance entry when read back.

    Full round trip: the mutation creates the model and its CREATE entry, then a
    separate myModel query re-fetches that entry by id. The persisted provenance —
    entry id, kind, and the linked task — must match what the mutation returned.
    """
    created = await create_model(task_headers, "round-trip")
    created_entry = created["provenance"][0]

    fetched = await get_model(task_headers, created["id"])

    assert fetched["id"] == created["id"]
    assert fetched["yourField"] == "round-trip"

    # The creation entry is recovered intact through the query path.
    assert len(fetched["provenance"]) == 1
    fetched_entry = fetched["provenance"][0]
    assert fetched_entry["id"] == created_entry["id"]
    assert fetched_entry["kind"] == "CREATE"
    assert fetched_entry["effectiveChanges"] == []

    # And it is still linked to the task that the mutation recorded, including the
    # executing agent client id and the single-use token id.
    assert fetched_entry["task"] == created_entry["task"]
    assert fetched_entry["task"]["assignationId"] == "task-1"
    assert fetched_entry["task"]["callerSub"] == "1"
    assert fetched_entry["task"]["agentClientId"] == "static"
    assert fetched_entry["task"]["tokenId"]  # jti is persisted and non-empty

    # The query path never spawned a second task row for the same assignation.
    assert await sync_to_async(Task.objects.count)() == 1


@pytest.mark.asyncio
async def test_agent_client_id_is_carried_through(transactional_db, auth_headers) -> None:
    """The token's agent client id (act.cid) is persisted and read back verbatim.

    Uses a distinctive client id so the value can only come from the token, proving
    the field is genuinely wired through create -> query rather than defaulted.
    """
    headers = {
        **auth_headers,
        "Rekuest-Task": provenance_token(tsk="task-cid", agent_cid="my-agent-client-7"),
    }

    created = await create_model(headers)
    created_task = created["provenance"][0]["task"]
    assert created_task["agentClientId"] == "my-agent-client-7"

    fetched = await get_model(headers, created["id"])
    fetched_task = fetched["provenance"][0]["task"]
    assert fetched_task["agentClientId"] == "my-agent-client-7"

    def check_row() -> None:
        task = Task.objects.get(assignation_id="task-cid")
        assert task.agent_client_id == "my-agent-client-7"

    await sync_to_async(check_row)()


@pytest.mark.asyncio
async def test_task_for_unknown_causer_is_unattributed(transactional_db, auth_headers) -> None:
    """An rcb with no local user row still records the task with a null assigner."""
    headers = {**auth_headers, "Rekuest-Task": provenance_token(tsk="task-3", rcb="ghost")}
    created = await create_model(headers)

    entry = created["provenance"][0]
    assert entry["task"] is not None
    assert entry["task"]["assignerSub"] == "ghost"

    def check_row() -> None:
        task = Task.objects.get(assignation_id="task-3")
        assert task.assigner is None
        assert task.assigner_sub == "ghost"

    await sync_to_async(check_row)()
