"""Find what a workflow created.

A workflow is a root task: every task it causes carries the root's id
(``Task.root_task_id``), so "created during the workflow" is a lookup on that id.
A model records its creation in one of two ways, and :func:`created_under`
picks the one it has:

- a ``created_through`` foreign key to :class:`~koherent.models.Task`, stamped
  when the object is created (the cheap path, an indexed join);
- otherwise its ``ProvenanceField`` history: the object's CREATE row ran under
  a task of the workflow.

A model with neither cannot say what created it, and :func:`created_under`
answers ``None`` so a caller never mistakes "unknown" for "nothing".
"""

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q
from simple_history.exceptions import NotHistoricalModelError
from simple_history.utils import get_history_model_for_model

from koherent.models import Task

CREATED_THROUGH = "created_through"
"""The conventional name of the foreign key a model stamps its creating task in."""

HISTORY_CREATE = "+"
"""simple_history's code for the history row of a creation."""


def records_creation_through(model: type[models.Model]) -> bool:
    """Whether ``model`` stamps the task that created it in ``created_through``."""
    try:
        field = model._meta.get_field(CREATED_THROUGH)
    except FieldDoesNotExist:
        return False
    return field.is_relation and field.related_model is Task


def created_under(
    model: type[models.Model], root_task_id: str, *, organization: object = None
) -> Q | None:
    """The rows of ``model`` created during the workflow ``root_task_id``.

    Held to ``organization``'s tasks when given: task ids are rekuest's, and a workflow is
    one organization's. Returns ``None`` when ``model`` records neither a creating task nor
    a history.
    """
    if records_creation_through(model):
        condition = Q(**{f"{CREATED_THROUGH}__root_task_id": root_task_id})
        if organization is not None:
            condition &= Q(**{f"{CREATED_THROUGH}__organization": organization})
        return condition
    try:
        history = get_history_model_for_model(model)
    except NotHistoricalModelError:
        return None
    pk = model._meta.pk
    assert pk is not None, f"{model.__name__} has no primary key"
    entries = history._default_manager.filter(
        task__root_task_id=root_task_id, history_type=HISTORY_CREATE
    )
    if organization is not None:
        entries = entries.filter(task__organization=organization)
    created = entries.values(pk.attname)
    return Q(pk__in=created)


__all__ = ["CREATED_THROUGH", "created_under", "records_creation_through"]
