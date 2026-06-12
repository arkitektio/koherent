"""End-to-end tests for provenance and task tracking over HTTP."""

import pytest
from asgiref.sync import sync_to_async

from test_project.asgi import application
from kante.testing import GraphQLHttpTestClient

from authentikate.models import Membership, Organization, User
from koherent.models import Task
from tests.conftest import task_header


CREATE_MODEL = """
mutation($yourField: String!) {
    createModel(yourField: $yourField) {
        id
        provenanceEntries {
            id
            kind
            effectiveChanges { field oldValue newValue }
            task {
                taskId
                assignerSub
                app
                action
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


@pytest.mark.asyncio
async def test_create_without_task(transactional_db, auth_headers) -> None:
    """Without a task header nothing is persisted and the entry has no task."""
    created = await create_model(auth_headers)

    assert created["id"] is not None
    entry = created["provenanceEntries"][0]
    assert entry["kind"] == "CREATE"
    # The creation entry has no previous record to diff against.
    assert entry["effectiveChanges"] == []
    assert entry["task"] is None
    assert await sync_to_async(Task.objects.count)() == 0


@pytest.mark.asyncio
async def test_task_created(transactional_db, task_headers) -> None:
    """A validated task header creates one task row linked from the history entry."""
    created = await create_model(task_headers)

    entry = created["provenanceEntries"][0]
    assert entry["task"] is not None
    assert entry["task"]["taskId"] == "task-1"
    assert entry["task"]["assignerSub"] == "1"
    assert entry["task"]["app"] == "testapp"
    assert entry["task"]["action"] == "actionhash"

    def check_row() -> None:
        task = Task.objects.get(task_id="task-1")
        assert task.args == {"x": 1}
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
    """A task assigned by a same-org member resolves to that member's user row."""

    def seed() -> None:
        org, _ = Organization.objects.get_or_create(slug="static_org")
        assigner, _ = User.objects.get_or_create(
            sub="2", iss="static_issuer", defaults={"username": "static_issuer_2"}
        )
        Membership.objects.get_or_create(user=assigner, organization=org)

    await sync_to_async(seed)()

    headers = {**auth_headers, "Rekuest-Task": task_header(task_id="task-2", user="2")}
    await create_model(headers)

    def check_row() -> None:
        task = Task.objects.get(task_id="task-2")
        assert task.assigner is not None
        assert task.assigner.sub == "2"
        assert task.assigner_sub == "2"

    await sync_to_async(check_row)()


@pytest.mark.asyncio
async def test_task_for_non_member_rejected(transactional_db, auth_headers) -> None:
    """A task assigned by an unknown user is rejected before any resolver runs."""
    headers = {**auth_headers, "Rekuest-Task": task_header(task_id="task-3", user="ghost")}
    client = GraphQLHttpTestClient(application=application, headers=headers)

    try:
        answer = await client.execute(CREATE_MODEL, variables={"yourField": "nope"})
    except Exception:
        answer = None

    if answer is not None:
        assert not (answer.get("data") or {}).get("createModel"), (
            f"Expected the mutation to be rejected {answer}"
        )

    assert await sync_to_async(Task.objects.count)() == 0
