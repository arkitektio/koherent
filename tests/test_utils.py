"""Unit tests for koherent.utils.get_or_create_task."""

import pytest

from authentikate.base_models import StaticToken, Task as TaskPayload
from authentikate.models import Organization, User
from authentikate.vars import organization_var, token_var, user_var
from koherent.models import Task
from koherent.utils import get_or_create_task
from koherent.vars import current_task, current_task_payload


@pytest.fixture
def auth_context(db):
    """A request-like auth context for the static "test" identity."""
    user = User.objects.create(sub="1", iss="static_issuer", username="static_issuer_1")
    org = Organization.objects.create(slug="static_org")
    token = StaticToken(sub="1")

    resets = [
        (token_var, token_var.set(token)),
        (user_var, user_var.set(user)),
        (organization_var, organization_var.set(org)),
        # Tests run in one thread, so a cached row from a previous test (whose
        # transaction was rolled back) would leak through the context variable.
        (current_task, current_task.set(None)),
    ]
    yield user, org
    for var, reset in resets:
        var.reset(reset)


def _payload(user: str, task_id: str = "task-x") -> TaskPayload:
    return TaskPayload(id=task_id, args={"a": 1}, user=user, app="testapp", action="hash")


def test_no_task_returns_none(auth_context) -> None:
    """Without a current task payload there is nothing to persist."""
    assert get_or_create_task() is None
    assert Task.objects.count() == 0


def test_assigner_is_request_user(auth_context) -> None:
    """When the task user matches the token sub, the request user is the assigner."""
    user, org = auth_context
    reset = current_task_payload.set(_payload(user="1"))
    try:
        task = get_or_create_task()
        assert task is not None
        assert task.assigner == user
        assert task.assigner_sub == "1"
        assert task.organization == org
        # Repeated calls return the cached row without duplicating it.
        assert get_or_create_task() == task
        assert Task.objects.count() == 1
    finally:
        current_task_payload.reset(reset)


def test_unresolvable_assigner_keeps_raw_sub(auth_context) -> None:
    """An assigner sub with no local user row falls back to null + raw sub."""
    reset = current_task_payload.set(_payload(user="ghost", task_id="task-y"))
    try:
        task = get_or_create_task()
        assert task is not None
        assert task.assigner is None
        assert task.assigner_sub == "ghost"
    finally:
        current_task_payload.reset(reset)


def test_no_organization_returns_none(auth_context) -> None:
    """Without an organization in the auth context nothing is persisted."""
    reset_org = organization_var.set(None)
    reset_payload = current_task_payload.set(_payload(user="1", task_id="task-z"))
    try:
        assert get_or_create_task() is None
        assert Task.objects.count() == 0
    finally:
        current_task_payload.reset(reset_payload)
        organization_var.reset(reset_org)


def test_payload_fields_are_persisted(auth_context) -> None:
    """parent, args, app and action from the payload land on the task row."""
    payload = TaskPayload(
        id="task-f", parent="parent-1", args={"a": 1}, user="1", app="testapp", action="hash"
    )
    reset = current_task_payload.set(payload)
    try:
        task = get_or_create_task()
        assert task is not None
        assert task.parent_id == "parent-1"
        assert task.args == {"a": 1}
        assert task.app == "testapp"
        assert task.action == "hash"
    finally:
        current_task_payload.reset(reset)


def test_cache_misses_on_new_task_id(auth_context) -> None:
    """A payload with a different task id bypasses the cached row."""
    reset = current_task_payload.set(_payload(user="1", task_id="task-a"))
    try:
        first = get_or_create_task()
    finally:
        current_task_payload.reset(reset)

    reset = current_task_payload.set(_payload(user="1", task_id="task-b"))
    try:
        second = get_or_create_task()
        assert second is not None
        assert second != first
        assert Task.objects.count() == 2
    finally:
        current_task_payload.reset(reset)


def test_concurrent_create_race_resolves_existing_row(auth_context, monkeypatch) -> None:
    """When a concurrent request wins the insert race, the existing row is used."""
    from django.db import IntegrityError

    user, org = auth_context
    existing = Task.objects.create(
        task_id="task-race",
        assigner=user,
        assigner_sub="1",
        app="testapp",
        action="hash",
        organization=org,
    )

    def lost_race(**kwargs):
        raise IntegrityError("duplicate key value violates unique constraint")

    monkeypatch.setattr(Task.objects, "get_or_create", lost_race)
    reset = current_task_payload.set(_payload(user="1", task_id="task-race"))
    try:
        assert get_or_create_task() == existing
        assert Task.objects.count() == 1
    finally:
        current_task_payload.reset(reset)
