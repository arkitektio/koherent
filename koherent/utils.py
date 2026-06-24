import logging
from typing import TYPE_CHECKING

from authentikate.vars import get_organization, get_token, get_user
from koherent.vars import current_provenance, current_task

if TYPE_CHECKING:
    from koherent.models import Task

logger = logging.getLogger(__name__)


def get_or_create_task() -> "Task | None":
    """Get (creating on first use) the Task row for the request's provenance token.

    Returns None when the request did not carry a verified provenance token.
    The row is cached in a context variable so repeated calls within one
    request (e.g. several history signals) hit the database at most once.

    An existing row is returned as-is, even when the auth context carries no
    organization; the organization is only required to create the row.

    Sync only: call from sync resolvers and signals.
    """
    from django.contrib.auth import get_user_model
    from django.db import IntegrityError

    from koherent.models import Task

    provenance = current_provenance.get()
    if provenance is None:
        return None

    cached = current_task.get()
    if cached is not None and cached.task_id == provenance.tsk:
        return cached

    # Warm path first: long-running tasks span many requests, so the row
    # usually exists and the assigner resolution query can be skipped.
    task = Task.objects.filter(task_id=provenance.tsk).first()

    if task is None:
        organization = get_organization()
        if organization is None:
            logger.warning(
                "Cannot persist provenance task %s: no organization in the auth context",
                provenance.tsk,
            )
            return None

        token = get_token()
        user = get_user()
        # Attribute the change to the human at the root of the causal tree (rcb).
        if user is not None and provenance.rcb == user.sub:
            assigner = user
        else:
            assigner = (
                get_user_model()
                .objects.filter(
                    sub=provenance.rcb, iss=token.iss if token else None
                )
                .first()
            )

        try:
            task = Task.objects.create(
                task_id=provenance.tsk,
                parent_task_id=provenance.ptk,
                root_task_id=provenance.rtk,
                assigner=assigner,
                assigner_sub=provenance.rcb,
                caller_sub=provenance.sub,
                agent_sub=provenance.act.sub,
                agent_client_id=provenance.act.cid,
                issuer=provenance.iss,
                token_id=provenance.jti,
                args_hash=provenance.ahs,
                args_hash_algorithm=provenance.aha,
                organization=organization,
            )
        except IntegrityError:
            # A concurrent request for the same task won the race; the row
            # exists now.
            task = Task.objects.get(task_id=provenance.tsk)

    current_task.set(task)
    return task
