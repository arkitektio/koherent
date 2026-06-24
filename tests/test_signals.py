"""Unit tests for the pre_create_historical_record signal handler."""

import pytest

from authentikate.base_models import StaticToken
from authentikate.models import Client, Organization, User
from authentikate.vars import client_var, organization_var, token_var, user_var
from koherent.vars import current_provenance, current_task
from testing_module.models import MyModel
from tests.conftest import provenance_obj


@pytest.fixture
def request_context(db):
    """A full request-like auth context: user, client, org, token and provenance."""
    user = User.objects.create(sub="1", iss="static_issuer", username="static_issuer_1")
    org = Organization.objects.create(slug="static_org")
    client = Client.objects.create(client_id="client-1", iss="static_issuer")
    provenance = provenance_obj(tsk="task-s", rcb="1")

    resets = [
        (token_var, token_var.set(StaticToken(sub="1"))),
        (user_var, user_var.set(user)),
        (client_var, client_var.set(client)),
        (organization_var, organization_var.set(org)),
        (current_provenance, current_provenance.set(provenance)),
        (current_task, current_task.set(None)),
    ]
    yield user, client
    for var, reset in resets:
        var.reset(reset)


@pytest.fixture
def no_context(db):
    """An explicitly empty auth context (guards against contextvar leaks)."""
    resets = [
        (token_var, token_var.set(None)),
        (user_var, user_var.set(None)),
        (client_var, client_var.set(None)),
        (organization_var, organization_var.set(None)),
        (current_provenance, current_provenance.set(None)),
        (current_task, current_task.set(None)),
    ]
    yield
    for var, reset in resets:
        var.reset(reset)


def test_history_entry_is_attributed(request_context) -> None:
    """Creating a model under a request context attributes the history entry."""
    user, client = request_context
    model = MyModel.objects.create(your_field="a")

    entry = model.provenance_entries.get()
    assert entry.history_user == user
    assert entry.client == client
    assert entry.task is not None
    assert entry.task.task_id == "task-s"


def test_updates_share_the_request_task(request_context) -> None:
    """Every change within one request context links to the same task row."""
    model = MyModel.objects.create(your_field="a")
    model.your_field = "b"
    model.save()

    tasks = {entry.task_id for entry in model.provenance_entries.all()}
    assert len(model.provenance_entries.all()) == 2
    assert len(tasks) == 1


def test_history_entry_without_context_is_unattributed(no_context) -> None:
    """Without an auth context the entry is recorded with empty attribution."""
    model = MyModel.objects.create(your_field="a")

    entry = model.provenance_entries.get()
    assert entry.history_user is None
    assert entry.client is None
    assert entry.task is None
