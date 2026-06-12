import contextvars
from typing import TYPE_CHECKING

from authentikate.base_models import Task as TaskPayload

if TYPE_CHECKING:
    from koherent.models import Task


current_task_payload: contextvars.ContextVar[TaskPayload | None] = (
    contextvars.ContextVar("current_task_payload", default=None)
)
current_task: contextvars.ContextVar["Task | None"] = contextvars.ContextVar(
    "current_task", default=None
)


def get_current_task_payload() -> TaskPayload | None:
    """
    Get the current validated Rekuest task payload from the context variable

    Returns
    -------
    TaskPayload | None
        The current task payload
    """
    return current_task_payload.get()
