import logging
from typing import TYPE_CHECKING

from authentikate.vars import get_organization, get_token, get_user
from koherent.vars import current_task, current_task_payload

if TYPE_CHECKING:
    from koherent.models import Task

logger = logging.getLogger(__name__)


def get_or_create_task() -> "Task | None":
    """Get (creating on first use) the Task row for the request's task payload.

    Returns None when the request did not carry a validated Rekuest task.
    The row is cached in a context variable so repeated calls within one
    request (e.g. several history signals) hit the database at most once.

    Sync only: call from sync resolvers and signals.
    """
    from django.contrib.auth import get_user_model
    from django.db import IntegrityError

    from koherent.models import Task

    payload = current_task_payload.get()
    if payload is None:
        return None

    cached = current_task.get()
    if cached is not None and cached.task_id == payload.id:
        return cached

    organization = get_organization()
    if organization is None:
        logger.warning(
            "Cannot persist task %s: no organization in the auth context", payload.id
        )
        return None

    token = get_token()
    user = get_user()
    if user is not None and payload.user == user.sub:
        assigner = user
    else:
        # authentikate's validate_task_assignment already proved a same-org
        # membership exists for this sub; resolve it to the local user row.
        assigner = (
            get_user_model()
            .objects.filter(sub=payload.user, iss=token.iss if token else None)
            .first()
        )

    try:
        task, _ = Task.objects.get_or_create(
            task_id=payload.id,
            defaults=dict(
                parent_id=payload.parent,
                assigner=assigner,
                assigner_sub=payload.user,
                app=payload.app,
                action=payload.action,
                args=payload.args,
                organization=organization,
            ),
        )
    except IntegrityError:
        # A concurrent request for the same task won the race; the row exists now.
        task = Task.objects.get(task_id=payload.id)

    current_task.set(task)
    return task
