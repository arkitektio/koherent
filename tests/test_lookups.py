"""``created_under``: what a workflow (a root task) created, whichever way a model records it."""

import pytest
from authentikate.models import Organization

from koherent.lookups import created_under
from koherent.models import Task
from testing_module.models import MyModel, PlainModel, StampedModel
from tests.conftest import provenance_token
from tests.test_filters import create_model, filter_models, update_model


def _task(organization: Organization, task_id: str, root: str) -> Task:
    return Task.objects.create(
        task_id=task_id,
        root_task_id=root,
        assigner_sub="1",
        caller_sub="1",
        agent_sub="1",
        agent_client_id="static",
        issuer="rekuest",
        token_id=f"jti-{task_id}",
        args_hash="x",
        args_hash_algorithm="x",
        organization=organization,
    )


@pytest.mark.django_db
def test_stamped_model_matches_through_created_through() -> None:
    """A model with ``created_through`` matches every task of the workflow, root or child."""
    organization = Organization.objects.create(slug="org-lookups")
    root = _task(organization, "root-1", "root-1")
    child = _task(organization, "child-1", "root-1")
    other = _task(organization, "root-2", "root-2")
    by_root = StampedModel.objects.create(name="a", created_through=root)
    by_child = StampedModel.objects.create(name="b", created_through=child)
    StampedModel.objects.create(name="c", created_through=other)
    StampedModel.objects.create(name="d")

    q = created_under(StampedModel, "root-1")
    assert q is not None
    assert set(StampedModel.objects.filter(q)) == {by_root, by_child}

    elsewhere = Organization.objects.create(slug="org-elsewhere")
    q = created_under(StampedModel, "root-1", organization=elsewhere)
    assert q is not None
    assert not StampedModel.objects.filter(q).exists()


def test_a_model_recording_nothing_answers_none() -> None:
    """Unknown is not nothing: a model without a task stamp or history says so."""
    assert created_under(PlainModel, "root-1") is None


@pytest.mark.asyncio
async def test_history_model_matches_its_creation_only(
    transactional_db: None, auth_headers: dict[str, str]
) -> None:
    """Through the history, only the CREATE row counts: a later edit doesn't adopt the object."""
    in_workflow = await create_model(
        {**auth_headers, "Rekuest-Task": provenance_token(tsk="w-child", root="w")}
    )
    edited_later = await create_model(
        {**auth_headers, "Rekuest-Task": provenance_token(tsk="elsewhere")}
    )
    await update_model(
        {**auth_headers, "Rekuest-Task": provenance_token(tsk="w-later", root="w")},
        edited_later,
        "changed",
    )

    q = created_under(MyModel, "w")
    assert q is not None
    ids = [
        str(pk) async for pk in MyModel.objects.filter(q).values_list("pk", flat=True)
    ]
    assert ids == [in_workflow]

    # The provenance filter's rootTaskId matches any change, edits included.
    changed = await filter_models(auth_headers, {"provenance": {"rootTaskId": "w"}})
    assert {m["id"] for m in changed} == {in_workflow, edited_later}
