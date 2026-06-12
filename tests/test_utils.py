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
